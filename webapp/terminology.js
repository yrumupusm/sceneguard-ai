/* Display-only vocabulary. Stored states, API payloads and review input stay intact. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document !== 'undefined') {
    root.SceneGuardPublicText = api;
    api.install(document);
  }
})(globalThis, function () {
  'use strict';
  function text(value) {
    if (typeof value !== 'string') return value;
    return value
      .replace(/자동[ \t]*침입[ \t]*확인/g, '침입 검출')
      .replace(/침입[ \t]*확인[ \t]*(?:[·ㆍ/][ \t]*자동|\([ \t]*자동[ \t]*\))/g, '침입 검출')
      .replace(/침입[ \t]*자동[ \t]*확인/g, '침입 검출')
      .replace(/자동[ \t]*확인/g, '침입 검출')
      .replace(/침입[ \t]*확인/g, '침입 검출')
      .replace(/침입 침입 검출/g, '침입 검출')
      .replace(/침입 검출으로/g, '침입 검출로');
  }
  function skip(node) {
    for (let p = node.nodeType === 1 ? node : node.parentNode; p; p = p.parentNode) {
      if (/^(SCRIPT|STYLE|TEXTAREA|INPUT|CODE|PRE)$/.test(p.tagName || '') || p.isContentEditable) return true;
    }
    return false;
  }
  function visit(node) {
    if (!node || skip(node)) return;
    if (node.nodeType === 3) {
      const next = text(node.nodeValue);
      if (next !== node.nodeValue) node.nodeValue = next;
      return;
    }
    if (node.nodeType === 1 && typeof node.getAttribute === 'function') {
      for (const key of ['title','aria-label']) {
        const old = node.getAttribute(key);
        const next = text(old);
        if (old !== next) node.setAttribute(key, next);
      }
    }
    for (const child of Array.from(node.childNodes || [])) visit(child);
  }
  function install(doc) {
    if (!doc.body) {
      doc.addEventListener('DOMContentLoaded', () => install(doc), {once:true});
      return null;
    }
    visit(doc.body);
    if (typeof MutationObserver === 'undefined') return null;
    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'childList') {
          for (const child of record.addedNodes) visit(child);
        } else visit(record.target);
      }
    });
    observer.observe(doc.body, {subtree:true, childList:true, characterData:true,
      attributes:true, attributeFilter:['title','aria-label']});
    return observer;
  }
  return {text, visit, install};
});
