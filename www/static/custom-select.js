(function () {
  'use strict';

  let idCounter = 0;
  const activeOverlays = new Set();

  function enhanceSelect(select) {
    if (select.closest('.custom-select')) return;
    if (!select.id && !select.classList.contains('trip-category')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select';
    wrapper.dataset.csId = ++idCounter;

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    select.style.position = 'absolute';
    select.style.opacity = '0';
    select.style.pointerEvents = 'none';
    select.style.width = '1px';
    select.style.height = '1px';
    select.style.left = '0';
    select.style.top = '0';

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'cs-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    const labelSpan = document.createElement('span');
    labelSpan.className = 'cs-label';
    labelSpan.textContent = select.options[select.selectedIndex]?.text || '';

    const arrow = document.createElement('span');
    arrow.className = 'cs-arrow';

    trigger.appendChild(labelSpan);
    trigger.appendChild(arrow);
    wrapper.appendChild(trigger);

    const overlay = document.createElement('div');
    overlay.className = 'cs-overlay';
    overlay.setAttribute('role', 'listbox');
    overlay.setAttribute('tabindex', '-1');

    const sheet = document.createElement('div');
    sheet.className = 'cs-sheet';

    const header = document.createElement('div');
    header.className = 'cs-header';

    const title = document.createElement('span');
    title.className = 'cs-title';
    title.textContent = (select.previousElementSibling?.textContent || '请选择').trim();

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'cs-close';
    closeBtn.setAttribute('aria-label', '关闭');
    closeBtn.textContent = '×';

    header.appendChild(title);
    header.appendChild(closeBtn);

    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'cs-options';

    function buildOptions() {
      optionsContainer.innerHTML = '';
      Array.from(select.options).forEach((opt, idx) => {
        const div = document.createElement('div');
        div.className = 'cs-option' + (opt.selected ? ' selected' : '');
        div.setAttribute('role', 'option');
        div.setAttribute('data-value', opt.value);
        div.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
        div.textContent = opt.text;
        div.addEventListener('click', () => {
          select.selectedIndex = idx;
          select.dispatchEvent(new Event('change', { bubbles: true }));
          updateLabel();
          closeOverlay(wrapper);
        });
        optionsContainer.appendChild(div);
      });
    }

    buildOptions();

    sheet.appendChild(header);
    sheet.appendChild(optionsContainer);
    overlay.appendChild(sheet);
    wrapper.appendChild(overlay);

    function updateLabel() {
      const opt = select.options[select.selectedIndex];
      labelSpan.textContent = opt ? opt.text : '';
      buildOptions();
    }

    function openOverlay() {
      activeOverlays.forEach(w => closeOverlay(w));
      overlay.classList.add('active');
      trigger.setAttribute('aria-expanded', 'true');
      activeOverlays.add(wrapper);

      const sel = optionsContainer.querySelector('.cs-option.selected');
      if (sel) sel.scrollIntoView({ block: 'nearest' });
    }

    function closeOverlay(targetWrapper) {
      const ow = (targetWrapper || wrapper).querySelector('.cs-overlay');
      if (ow) ow.classList.remove('active');
      const tr = (targetWrapper || wrapper).querySelector('.cs-trigger');
      if (tr) tr.setAttribute('aria-expanded', 'false');
      activeOverlays.delete(targetWrapper || wrapper);
    }

    trigger.addEventListener('click', (e) => {
      e.preventDefault();
      if (overlay.classList.contains('active')) {
        closeOverlay(wrapper);
      } else {
        openOverlay();
      }
    });

    closeBtn.addEventListener('click', () => closeOverlay(wrapper));
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeOverlay(wrapper);
    });

    select.addEventListener('change', updateLabel);

    trigger.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openOverlay();
      }
    });
    overlay.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeOverlay(wrapper);
        trigger.focus();
      }
    });
  }

  function initCustomSelects(root) {
    const targets = root.querySelectorAll
      ? root.querySelectorAll('select.trip-category, select#limit-category, select#ai-model')
      : [];
    targets.forEach(enhanceSelect);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initCustomSelects(document));
  } else {
    initCustomSelects(document);
  }

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType !== 1) continue;
        if (node.matches && (
          node.matches('select.trip-category') ||
          node.matches('select#limit-category') ||
          node.matches('select#ai-model')
        )) {
          enhanceSelect(node);
        }
        if (node.querySelectorAll) {
          initCustomSelects(node);
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  window.initCustomSelects = initCustomSelects;
  window.enhanceSelect = enhanceSelect;
})();
