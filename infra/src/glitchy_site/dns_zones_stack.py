"""The Route 53 hosted zones of glitchy.games and glitchygames.ai.

Its own stack, deployed first: the certificates in the other stacks validate through these zones,
which answer only once Namecheap names their servers (spec, Manual steps). The zones hold no
email records: the owner uses no email at these domains yet (spec, Risks).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aws_cdk
from aws_cdk import aws_route53 as route53

from glitchy_site.settings import GLITCHY_GAMES_APEX, GLITCHYGAMES_AI_APEX

if TYPE_CHECKING:
    import constructs


class DnsZonesStack(aws_cdk.Stack):
    """Both domains' hosted zones, kept when the stack is deleted, with their name servers.

    Attributes:
        glitchy_games_zone: The glitchy.games zone.
        glitchygames_ai_zone: The glitchygames.ai zone.

    """

    def __init__(self, scope: constructs.Construct, construct_id: str, **kwargs: Any) -> None:
        """Build the zones and an output of each zone's name servers.

        Args:
            scope: The app.
            construct_id: The stack's name.
            **kwargs: Passed to ``aws_cdk.Stack`` (its ``env``).

        """
        super().__init__(scope, construct_id, **kwargs)
        self.glitchy_games_zone = self._zone(
            construct_id='GlitchyGamesZone', name=GLITCHY_GAMES_APEX
        )
        self.glitchygames_ai_zone = self._zone(
            construct_id='GlitchygamesAiZone', name=GLITCHYGAMES_AI_APEX
        )
        aws_cdk.CfnOutput(
            self,
            'GlitchyGamesNameServers',
            value=aws_cdk.Fn.join(',', self.glitchy_games_zone.hosted_zone_name_servers or []),
            description='Set these as custom DNS for glitchy.games at Namecheap',
        )
        aws_cdk.CfnOutput(
            self,
            'GlitchygamesAiNameServers',
            value=aws_cdk.Fn.join(',', self.glitchygames_ai_zone.hosted_zone_name_servers or []),
            description='Set these as custom DNS for glitchygames.ai at Namecheap',
        )

    def _zone(self, *, construct_id: str, name: str) -> route53.PublicHostedZone:
        """Return a public zone that outlives the stack.

        Args:
            construct_id: The zone's construct id.
            name: The domain.

        Returns:
            The zone.

        """
        zone = route53.PublicHostedZone(self, construct_id, zone_name=name)
        zone.apply_removal_policy(aws_cdk.RemovalPolicy.RETAIN)
        return zone
