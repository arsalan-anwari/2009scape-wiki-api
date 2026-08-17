/*
 * 2009scape Sphinx theme -- progressive enhancements.
 *
 * Everything here is optional: the page is fully readable and navigable with
 * JavaScript disabled. No dependencies, no build step.
 */

(function () {
  'use strict';

  function on(el, event, handler, options) {
    if (el) {
      el.addEventListener(event, handler, options);
    }
  }

  /* ------------------------------------------------------------------ *
   * Mobile sidebar
   * ------------------------------------------------------------------ */

  function setupSidebarToggle() {
    var sidebar = document.querySelector('.rs-sidebar');
    var backdrop = document.querySelector('.rs-sidebar-backdrop');
    var toggle = document.querySelector('[data-rs-toggle="sidebar"]');

    if (!sidebar || !toggle) {
      return;
    }

    function setOpen(open) {
      sidebar.classList.toggle('rs-open', open);
      if (backdrop) {
        backdrop.classList.toggle('rs-open', open);
      }
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    on(toggle, 'click', function () {
      setOpen(!sidebar.classList.contains('rs-open'));
    });

    on(backdrop, 'click', function () {
      setOpen(false);
    });

    on(document, 'keydown', function (event) {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    });

    // Navigating within the sidebar should dismiss the overlay.
    sidebar.addEventListener('click', function (event) {
      if (event.target.closest('a')) {
        setOpen(false);
      }
    });
  }

  /* ------------------------------------------------------------------ *
   * Collapsible global toctree
   * ------------------------------------------------------------------ */

  function setupCollapsibleToc() {
    var nav = document.querySelector('[data-rs-globaltoc]');
    if (!nav) {
      return;
    }

    var collapse = nav.dataset.rsCollapse === 'true';

    Array.prototype.forEach.call(nav.querySelectorAll('li'), function (item) {
      var sublist = item.querySelector(':scope > ul');
      var link = item.querySelector(':scope > a');
      if (!sublist || !link) {
        return;
      }

      item.classList.add('rs-has-children');

      var expanded = !collapse || item.classList.contains('current');
      item.classList.toggle('rs-collapsed', !expanded);

      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'rs-expand';
      button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      button.setAttribute(
        'aria-label',
        'Toggle child pages of ' + link.textContent.trim()
      );
      button.textContent = expanded ? '−' : '+';

      button.addEventListener('click', function (event) {
        event.preventDefault();
        var nowCollapsed = item.classList.toggle('rs-collapsed');
        button.textContent = nowCollapsed ? '+' : '−';
        button.setAttribute('aria-expanded', nowCollapsed ? 'false' : 'true');
      });

      item.insertBefore(button, link.nextSibling);
    });
  }

  /* ------------------------------------------------------------------ *
   * Copy buttons on code blocks
   * ------------------------------------------------------------------ */

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }

    // Fallback for pages served over plain http (e.g. a local preview).
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand('copy');
        resolve();
      } catch (error) {
        reject(error);
      } finally {
        document.body.removeChild(area);
      }
    });
  }

  function setupCopyButtons() {
    var blocks = document.querySelectorAll('.rs-content div.highlight');

    Array.prototype.forEach.call(blocks, function (block) {
      var pre = block.querySelector('pre');
      if (!pre || block.closest('.rs-highlight-wrapper')) {
        return;
      }

      var wrapper = document.createElement('div');
      wrapper.className = 'rs-highlight-wrapper';
      block.parentNode.insertBefore(wrapper, block);
      wrapper.appendChild(block);

      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'rs-copy-btn';
      button.textContent = 'Copy';
      button.setAttribute('aria-label', 'Copy code to clipboard');

      button.addEventListener('click', function () {
        // Line numbers live in a sibling cell, so `pre` holds only the code.
        var text = pre.innerText.replace(/\n$/, '');
        copyText(text).then(
          function () {
            button.textContent = 'Copied';
            button.dataset.rsCopied = 'true';
            window.setTimeout(function () {
              button.textContent = 'Copy';
              delete button.dataset.rsCopied;
            }, 1600);
          },
          function () {
            button.textContent = 'Failed';
            window.setTimeout(function () {
              button.textContent = 'Copy';
            }, 1600);
          }
        );
      });

      wrapper.appendChild(button);
    });
  }

  /* ------------------------------------------------------------------ *
   * Wrap wide tables so the page itself never scrolls sideways
   * ------------------------------------------------------------------ */

  function setupTableWrappers() {
    var tables = document.querySelectorAll('.rs-content table.docutils');

    Array.prototype.forEach.call(tables, function (table) {
      if (table.closest('.rs-table-wrapper') || table.closest('table')) {
        return;
      }
      var wrapper = document.createElement('div');
      wrapper.className = 'rs-table-wrapper';
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });
  }

  /* ------------------------------------------------------------------ *
   * "On this page" scrollspy
   * ------------------------------------------------------------------ */

  function setupScrollSpy() {
    var toc = document.querySelector('.rs-toc');
    if (!toc || !('IntersectionObserver' in window)) {
      return;
    }

    var links = {};
    var targets = [];

    Array.prototype.forEach.call(toc.querySelectorAll('a[href^="#"]'), function (link) {
      var id = decodeURIComponent(link.getAttribute('href').slice(1));
      if (!id) {
        return;
      }
      var target = document.getElementById(id);
      if (target) {
        links[id] = link;
        targets.push(target);
      }
    });

    if (!targets.length) {
      return;
    }

    var visible = new Set();

    function highlight() {
      var current = null;
      for (var i = 0; i < targets.length; i += 1) {
        if (visible.has(targets[i].id)) {
          current = targets[i].id;
          break;
        }
      }
      Object.keys(links).forEach(function (id) {
        links[id].classList.toggle('rs-active', id === current);
      });
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            visible.add(entry.target.id);
          } else {
            visible.delete(entry.target.id);
          }
        });
        highlight();
      },
      { rootMargin: '-10% 0px -70% 0px', threshold: 0 }
    );

    targets.forEach(function (target) {
      observer.observe(target);
    });
  }

  /* ------------------------------------------------------------------ *
   * Back to top
   * ------------------------------------------------------------------ */

  function setupBackToTop() {
    var button = document.querySelector('.rs-back-to-top');
    if (!button) {
      return;
    }

    function update() {
      button.classList.toggle('rs-visible', window.scrollY > 600);
    }

    on(window, 'scroll', update, { passive: true });
    on(button, 'click', function (event) {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      var brand = document.querySelector('.rs-brand');
      if (brand) {
        brand.focus({ preventScroll: true });
      }
    });

    update();
  }

  /* ------------------------------------------------------------------ *
   * Keyboard shortcut: "/" focuses the sidebar search field
   * ------------------------------------------------------------------ */

  function setupSearchShortcut() {
    if (document.body.dataset.rsSearchShortcut === 'false') {
      return;
    }

    on(document, 'keydown', function (event) {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }

      var active = document.activeElement;
      if (
        active &&
        (active.tagName === 'INPUT' ||
          active.tagName === 'TEXTAREA' ||
          active.isContentEditable)
      ) {
        return;
      }

      var field = document.querySelector('.rs-search input[name="q"]');
      if (field) {
        event.preventDefault();
        field.focus();
      }
    });
  }

  function init() {
    setupSidebarToggle();
    setupCollapsibleToc();
    setupCopyButtons();
    setupTableWrappers();
    setupScrollSpy();
    setupBackToTop();
    setupSearchShortcut();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
