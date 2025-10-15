# payments/models.py
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from wallet.models import Wallet, Transaction

User = get_user_model()


class DepositRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),   # agent has taken and funds locked
        ('paid', 'Paid'),           # user clicked "I have paid"
        ('completed', 'Completed'), # funds moved to user
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='deposit_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_deposits")
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_deposits")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True, default='Cash deposit via agent')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    receipt = models.ImageField(upload_to="receipts/", blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} - ₦{self.amount} ({self.status})"

    @classmethod
    def generate_reference(cls, wallet):
        # simple timestamp-based ref
        return f"DEP_{wallet.account_number}_{timezone.now().strftime('%Y%m%d%H%M%S')}"

    def accept(self, agent_user, countdown_minutes: int = 15):
        """
        Agent accepts the request:
        - Checks the agent has enough *available* balance (balance - locked_balance)
        - Locks the funds (agent_wallet.locked_balance += amount)
        - Sets agent, status='accepted', accepted_at and expires_at
        Returns True/False.
        """
        if self.status != 'pending':
            return False

        if not hasattr(agent_user, "profile") or not getattr(agent_user.profile, "is_agent", False):
            return False

        with transaction.atomic():
            # reload and lock rows
            dep = DepositRequest.objects.select_for_update().get(pk=self.pk)

            if dep.status != 'pending':
                return False

            # Lock agent wallet row and check funds
            try:
                agent_wallet = Wallet.objects.select_for_update().get(user=agent_user)
            except Wallet.DoesNotExist:
                return False

            # available = balance - locked_balance
            if (agent_wallet.balance - agent_wallet.locked_balance) < dep.amount:
                return False

            # increment locked_balance
            agent_wallet.locked_balance = agent_wallet.locked_balance + Decimal(dep.amount)
            agent_wallet.save(update_fields=['locked_balance'])

            # assign agent and mark accepted
            dep.agent = agent_user
            dep.status = 'accepted'
            dep.accepted_at = timezone.now()
            dep.expires_at = timezone.now() + timedelta(minutes=countdown_minutes)
            dep.save(update_fields=['agent', 'status', 'accepted_at', 'expires_at'])

        return True

    def mark_as_paid(self, receipt_file=None):
        """
        Called by the buyer/user when they say "I have paid".
        Changes status accepted -> paid and optionally attaches a receipt.
        """
        if self.status != 'accepted':
            return False

        with transaction.atomic():
            dep = DepositRequest.objects.select_for_update().get(pk=self.pk)
            if dep.status != 'accepted':
                return False
            if receipt_file:
                dep.receipt = receipt_file
            dep.status = 'paid'
            dep.save(update_fields=['status', 'receipt'] if receipt_file else ['status'])
        return True

    def confirm(self, agent_user=None):
        """
        Agent confirms and releases funds to user:
        - Expects status == 'paid' (user confirmed payment)
        - Deducts amount from agent_wallet.locked_balance and agent_wallet.balance
        - Credits amount to user wallet.balance
        - Creates a single 'transfer' Transaction record
        """
        if self.status != 'paid':
            return False

        with transaction.atomic():
            dep = DepositRequest.objects.select_for_update().get(pk=self.pk)
            if dep.status != 'paid':
                return False

            # load wallets
            try:
                agent_wallet = Wallet.objects.select_for_update().get(user=dep.agent)
            except Wallet.DoesNotExist:
                return False

            user_wallet = Wallet.objects.select_for_update().get(pk=dep.wallet.pk)

            if agent_wallet.locked_balance < dep.amount or agent_wallet.balance < dep.amount:
                # Something wrong with agent's funds
                return False

            # debit agent (locked_balance + balance)
            agent_wallet.locked_balance = agent_wallet.locked_balance - Decimal(dep.amount)
            agent_wallet.balance = agent_wallet.balance - Decimal(dep.amount)
            agent_wallet.save(update_fields=['locked_balance', 'balance'])

            # credit user
            user_wallet.balance = user_wallet.balance + Decimal(dep.amount)
            user_wallet.save(update_fields=['balance'])

            # transaction record (single transfer)
            Transaction.objects.create(
                transaction_type='transfer',
                amount=dep.amount,
                sender=agent_wallet,
                receiver=user_wallet,
                description=f'P2P transfer for {dep.reference}',
                status='completed',
            )

            # finalize deposit request
            dep.status = 'completed'
            dep.confirmed_at = timezone.now()
            dep.completed_at = timezone.now()
            dep.save(update_fields=['status', 'confirmed_at', 'completed_at'])

        return True

    def cancel_by_user(self):
        """User cancels when still pending."""
        if self.status != 'pending':
            return False
        self.status = 'cancelled'
        self.save(update_fields=['status'])
        return True

    def reject_by_agent(self):
        """Agent rejects a pending/accepted request and (if accepted) unlocks funds."""
        if self.status not in ('pending', 'accepted'):
            return False

        with transaction.atomic():
            dep = DepositRequest.objects.select_for_update().get(pk=self.pk)
            # if accepted, unlock agent funds
            if dep.status == 'accepted' and dep.agent:
                try:
                    agent_wallet = Wallet.objects.select_for_update().get(user=dep.agent)
                    if agent_wallet.locked_balance >= dep.amount:
                        agent_wallet.locked_balance = agent_wallet.locked_balance - Decimal(dep.amount)
                        agent_wallet.save(update_fields=['locked_balance'])
                except Wallet.DoesNotExist:
                    pass

            dep.status = 'rejected'
            dep.save(update_fields=['status'])
        return True

    def expire(self):
        """
        Called (e.g., by cron or view) when accepted request passes expires_at:
        - unlocks agent locked_balance (if any)
        - sets status to 'expired'
        """
        if self.status != 'accepted' or not self.expires_at:
            return False

        if timezone.now() <= self.expires_at:
            return False

        with transaction.atomic():
            dep = DepositRequest.objects.select_for_update().get(pk=self.pk)
            if dep.status != 'accepted':
                return False

            if dep.agent:
                try:
                    agent_wallet = Wallet.objects.select_for_update().get(user=dep.agent)
                    if agent_wallet.locked_balance >= dep.amount:
                        agent_wallet.locked_balance = agent_wallet.locked_balance - Decimal(dep.amount)
                        agent_wallet.save(update_fields=['locked_balance'])
                except Wallet.DoesNotExist:
                    pass

            dep.status = 'expired'
            dep.save(update_fields=['status'])
        return True



class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),   # agent accepted -> user's funds locked
        ('paid', 'Paid'),           # agent clicked "I have paid" and attached receipt
        ('completed', 'Completed'), # user confirmed - funds moved to agent
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawal_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_withdrawals")
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_withdrawals")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True, default='Cash withdrawal via agent')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)        # agent clicked "I have paid"
    confirmed_at = models.DateTimeField(null=True, blank=True)   # user clicked "confirm"
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    receipt = models.ImageField(upload_to="withdrawal_receipts/", blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} - ₦{self.amount} ({self.status})"

    @classmethod
    def generate_reference(cls, wallet):
        return f"WDR_{wallet.account_number}_{timezone.now().strftime('%Y%m%d%H%M%S')}"

    def accept(self, agent_user, countdown_minutes: int = 15):
        if self.status != "pending":
            return False

        if not hasattr(agent_user, "profile") or not getattr(agent_user.profile, "is_agent", False):
            return False

        with transaction.atomic():
            req = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)

            if req.status != "pending":
                return False

            try:
                user_wallet = Wallet.objects.select_for_update().get(pk=req.wallet.pk)
            except Wallet.DoesNotExist:
                return False

            if user_wallet.balance - user_wallet.locked_balance < req.amount:
                return False

            # Lock the user's funds for withdrawal
            user_wallet.locked_balance += req.amount
            user_wallet.save(update_fields=["locked_balance"])

            req.agent = agent_user
            req.status = "accepted"
            req.accepted_at = timezone.now()
            req.expires_at = timezone.now() + timedelta(minutes=countdown_minutes)
            req.save(update_fields=["agent", "status", "accepted_at", "expires_at"])

        return True




    def mark_as_paid(self, agent_user=None, receipt_file=None):
        """
        Called by the agent to indicate they've handed cash to the user.
        Change accepted -> paid and optionally attach a receipt.
        """
        if self.status != 'accepted':
            return False

        if agent_user and self.agent != agent_user:
            return False

        with transaction.atomic():
            req = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)
            if req.status != 'accepted':
                return False
            if receipt_file:
                req.receipt = receipt_file
            req.status = 'paid'
            req.paid_at = timezone.now()
            req.save(update_fields=['status', 'receipt', 'paid_at'] if receipt_file else ['status', 'paid_at'])
        return True

    def confirm(self, user=None):
        """
        User confirms a withdrawal:
        - Expects status == 'paid' (agent has handed cash)
        - Deducts amount from user's locked_balance and balance
        - Credits amount to agent's balance
        - Creates a 'transfer' transaction
        """
        if self.status != "paid":
            return False

        with transaction.atomic():
            req = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)

            if req.status != "paid":
                return False

            try:
                user_wallet = Wallet.objects.select_for_update().get(pk=req.wallet.pk)
                agent_wallet = Wallet.objects.select_for_update().get(user=req.agent)
            except Wallet.DoesNotExist:
                return False

            if user_wallet.locked_balance < req.amount or user_wallet.balance < req.amount:
                return False

            # debit user wallet
            user_wallet.locked_balance -= Decimal(req.amount)
            user_wallet.balance -= Decimal(req.amount)
            user_wallet.save(update_fields=["locked_balance", "balance"])

            # credit agent wallet
            agent_wallet.balance += Decimal(req.amount)
            agent_wallet.save(update_fields=["balance"])

            # create transfer transaction
            Transaction.objects.create(
                transaction_type="transfer",
                amount=req.amount,
                sender=user_wallet,
                receiver=agent_wallet,
                description=f"P2P transfer for {req.reference}",
                status="completed",
            )

            # finalize withdrawal request
            req.status = "completed"
            req.confirmed_at = timezone.now()
            req.completed_at = timezone.now()
            req.save(update_fields=["status", "confirmed_at", "completed_at"])

        return True





    def cancel_by_user(self):
        """User cancels when still pending."""
        if self.status != 'pending':
            return False
        self.status = 'cancelled'
        self.save(update_fields=['status'])
        return True

    def reject_by_agent(self):
        """Agent rejects a pending/accepted request and (if accepted) unlocks user's funds."""
        if self.status not in ('pending', 'accepted'):
            return False

        with transaction.atomic():
            req = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)
            # if accepted, unlock user funds
            if req.status == 'accepted' and req.wallet:
                try:
                    user_wallet = Wallet.objects.select_for_update().get(pk=req.wallet.pk)
                    if user_wallet.locked_balance >= req.amount:
                        user_wallet.locked_balance = user_wallet.locked_balance - Decimal(req.amount)
                        user_wallet.save(update_fields=['locked_balance'])
                except Wallet.DoesNotExist:
                    pass

            req.status = 'rejected'
            req.save(update_fields=['status'])
        return True

    def expire(self):
        """
        When accepted request passes expires_at: unlocks user's locked_balance and sets expired.
        """
        if self.status != 'accepted' or not self.expires_at:
            return False

        if timezone.now() <= self.expires_at:
            return False

        with transaction.atomic():
            req = WithdrawalRequest.objects.select_for_update().get(pk=self.pk)
            if req.status != 'accepted':
                return False

            if req.wallet:
                try:
                    user_wallet = Wallet.objects.select_for_update().get(pk=req.wallet.pk)
                    if user_wallet.locked_balance >= req.amount:
                        user_wallet.locked_balance = user_wallet.locked_balance - Decimal(req.amount)
                        user_wallet.save(update_fields=['locked_balance'])
                except Wallet.DoesNotExist:
                    pass

            req.status = 'expired'
            req.save(update_fields=['status'])
        return True




class Escrow(models.Model):
    """
    Optional bookkeeping Escrow record. We leave methods minimal because
    the "locking" and movement are handled on DepositRequest.
    """
    STATUS_CHOICES = [
        ('holding', 'Holding'),
        ('released', 'Released'),
        ('refunded', 'Refunded'),
    ]

    deposit_request = models.OneToOneField(DepositRequest, on_delete=models.CASCADE, related_name='escrow')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='holding')
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Escrow {self.deposit_request.reference} - ₦{self.amount} ({self.status})"
