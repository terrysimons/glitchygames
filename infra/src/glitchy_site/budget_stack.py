"""The account's monthly budget: an email before an AWS bill can surprise the owner.

The whole account (nothing else runs in it: the owner, 2026-10-28). The address comes from the
CDK context, never this repository (spec, Budget alarm).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aws_cdk
from aws_cdk import aws_budgets as budgets

if TYPE_CHECKING:
    import constructs

    from glitchy_site.settings import SiteSettings

ALERT_THRESHOLD_PERCENT = 100
"""Alert when the actual, or the forecast, monthly spend passes the whole budget."""


class BudgetStack(aws_cdk.Stack):
    """A monthly cost budget that emails at its limit, actual and forecast."""

    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        *,
        settings: SiteSettings,
        **kwargs: Any,
    ) -> None:
        """Build the budget.

        Args:
            scope: The app.
            construct_id: The stack's name.
            settings: The limit and the address to alert.
            **kwargs: Passed to ``aws_cdk.Stack`` (its ``env``).

        """
        super().__init__(scope, construct_id, **kwargs)
        subscribers = [
            budgets.CfnBudget.SubscriberProperty(
                subscription_type='EMAIL', address=settings.budget_alert_email
            )
        ]
        budgets.CfnBudget(
            self,
            'MonthlyBudget',
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name='glitchy-games-monthly',
                budget_type='COST',
                time_unit='MONTHLY',
                budget_limit=budgets.CfnBudget.SpendProperty(
                    amount=settings.budget_limit_usd, unit='USD'
                ),
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type=notification_type,
                        comparison_operator='GREATER_THAN',
                        threshold=ALERT_THRESHOLD_PERCENT,
                        threshold_type='PERCENTAGE',
                    ),
                    subscribers=subscribers,
                )
                for notification_type in ('ACTUAL', 'FORECASTED')
            ],
        )
