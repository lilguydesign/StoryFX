"""Closed, non-sensitive publication failure stages. No provider contents or errors."""
from typing import Literal

Evidence = Literal['own_status_verified', 'provider_ui_verified', 'result_uncertain',
                   'preflight_refused', 'album_media_unavailable', 'provider_not_ready',
                   'updates_navigation_failed', 'own_status_unavailable',
                   'share_selection_refused', 'contacts_preview_refused']
BEFORE_PUBLICATION = frozenset({'preflight_refused', 'album_media_unavailable',
                               'provider_not_ready', 'updates_navigation_failed',
                               'own_status_unavailable', 'share_selection_refused',
                               'contacts_preview_refused'})


def native_proof(state, evidence):
    return (evidence in BEFORE_PUBLICATION if state == 'FAILED_BEFORE_PUBLICATION' else
            state in {'CONFIRMED', 'NEEDS_REVIEW'} and
            evidence == {'CONFIRMED': 'own_status_verified',
                         'NEEDS_REVIEW': 'result_uncertain'}[state])
