/**
 * Confluence Application Entrypoint
 * Binds global keyboard handlers, smooth navigation scroll, and initializes live telemetry state.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global Escape key dismisses modals and slide-over drawers
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (typeof closeInspector === 'function') closeInspector();
      if (typeof closeChatDrawer === 'function') closeChatDrawer();
    }
  });

  // Initialize Chennai Coast as the default active station
  if (typeof switchStation === 'function') {
    switchStation('Chennai Coast', 13.08, 80.27, 'Tamil Nadu, Bay of Bengal');
  }
});
