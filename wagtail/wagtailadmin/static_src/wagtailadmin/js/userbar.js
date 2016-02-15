'use strict';

document.addEventListener('DOMContentLoaded', function userBar(e) {
    var userbar = document.querySelector('[data-wagtail-userbar]');
    var trigger = userbar.querySelector('[data-wagtail-userbar-trigger]');
    var list = userbar.querySelector('ul');
    var className = 'is-active';
    var hasTouch = 'ontouchstart' in window;
    var clickEvent = hasTouch ? 'touchstart' : 'click';

    if (!'classList' in userbar) {
        return;
    }

    if (hasTouch) {
        userbar.classList.add('touch');
    } else {
        userbar.classList.add('no-touch');
    }

    trigger.addEventListener(clickEvent, toggleUserbar, false);

    // make sure userbar is hidden when navigating back
    window.addEventListener('pageshow', hideUserbar, false);

    function showUserbar(e) {
        userbar.classList.add(className);
        list.addEventListener(clickEvent, sandboxClick, false);
        window.addEventListener(clickEvent, clickOutside, false);
    }

    function hideUserbar(e) {
        userbar.classList.remove(className);
        list.addEventListener(clickEvent, sandboxClick, false);
        window.removeEventListener(clickEvent, clickOutside, false);
    }

    function toggleUserbar(e) {
        e.stopPropagation();
        if (userbar.classList.contains(className)) {
            hideUserbar();
        } else {
            showUserbar();
        }
    }

    function sandboxClick(e) {
        e.stopPropagation();
    }

    function clickOutside(e) {
        hideUserbar();
    }
});
