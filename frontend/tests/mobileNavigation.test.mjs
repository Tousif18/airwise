import test from "node:test";
import assert from "node:assert/strict";
import {
  handleMobileNavigationKeyDown,
  restoreMobileNavigationFocus,
  setMobileNavigationOpen,
} from "../src/utils/mobileNavigation.js";

function createFocusableElement() {
  return {
    focused: false,
    getClientRects: () => [{}],
    focus() {
      this.focused = true;
    },
  };
}

function createEvent({ key, shiftKey = false }) {
  return {
    key,
    shiftKey,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
}

test("mobile navigation can be opened and closed", () => {
  const states = [];
  setMobileNavigationOpen((value) => states.push(value), true);
  setMobileNavigationOpen((value) => states.push(value), false);
  assert.deepEqual(states, [true, false]);
});

test("Escape closes the mobile navigation", () => {
  let closed = false;
  handleMobileNavigationKeyDown(
    createEvent({ key: "Escape" }),
    null,
    () => {
      closed = true;
    },
    null
  );
  assert.equal(closed, true);
});

test("Tab from the last item wraps focus to the first item", () => {
  const first = createFocusableElement();
  const last = createFocusableElement();
  const sidebar = { querySelectorAll: () => [first, last] };
  const event = createEvent({ key: "Tab" });

  handleMobileNavigationKeyDown(event, sidebar, () => {}, last);

  assert.equal(event.defaultPrevented, true);
  assert.equal(first.focused, true);
});

test("Shift+Tab from the first item wraps focus to the last item", () => {
  const first = createFocusableElement();
  const last = createFocusableElement();
  const sidebar = { querySelectorAll: () => [first, last] };
  const event = createEvent({ key: "Tab", shiftKey: true });

  handleMobileNavigationKeyDown(event, sidebar, () => {}, first);

  assert.equal(event.defaultPrevented, true);
  assert.equal(last.focused, true);
});

test("opening the menu focuses its close button", () => {
  const closeButton = createFocusableElement();
  const menuButton = createFocusableElement();

  restoreMobileNavigationFocus({
    isOpen: true,
    isMobile: true,
    closeButton,
    menuButton,
  });

  assert.equal(closeButton.focused, true);
  assert.equal(menuButton.focused, false);
});

test("closing the menu on mobile restores focus to its trigger", () => {
  const closeButton = createFocusableElement();
  const menuButton = createFocusableElement();

  restoreMobileNavigationFocus({
    isOpen: false,
    isMobile: true,
    closeButton,
    menuButton,
  });

  assert.equal(menuButton.focused, true);
  assert.equal(closeButton.focused, false);
});

test("closing the menu on desktop does not focus the hidden mobile trigger", () => {
  const menuButton = createFocusableElement();

  restoreMobileNavigationFocus({
    isOpen: false,
    isMobile: false,
    closeButton: null,
    menuButton,
  });

  assert.equal(menuButton.focused, false);
});
