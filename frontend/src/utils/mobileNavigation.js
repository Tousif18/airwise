export function setMobileNavigationOpen(onToggleMobile, isOpen) {
  onToggleMobile(isOpen);
}

export function restoreMobileNavigationFocus({
  isOpen,
  isMobile,
  closeButton,
  menuButton,
}) {
  if (isOpen) {
    closeButton?.focus();
  } else if (isMobile) {
    menuButton?.focus();
  }
}

export function handleMobileNavigationKeyDown(event, sidebar, closeMenu, activeElement) {
  if (event.key === "Escape") {
    closeMenu();
    return;
  }

  if (event.key !== "Tab" || !sidebar) return;

  const focusableElements = sidebar.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  const visibleElements = Array.from(focusableElements).filter(
    (element) => element.getClientRects().length > 0
  );

  if (visibleElements.length === 0) {
    event.preventDefault();
    return;
  }

  const firstElement = visibleElements[0];
  const lastElement = visibleElements[visibleElements.length - 1];

  if (event.shiftKey && activeElement === firstElement) {
    event.preventDefault();
    lastElement.focus();
  } else if (!event.shiftKey && activeElement === lastElement) {
    event.preventDefault();
    firstElement.focus();
  }
}
