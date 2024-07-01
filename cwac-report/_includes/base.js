//Manage in-page links by adding tabindex="-1" to non-focusable elements, and removing tabindex onblur/onfocusout.
//Based on https://github.com/selfthinker/dokuwiki_template_writr/blob/master/js/skip-link-focus-fix.js
//============================================
function manageInpageLinks() {

    if (Element && !Element.prototype.matches) {
        var proto = Element.prototype;
        proto.matches = proto.matchesSelector ||
            proto.mozMatchesSelector || proto.msMatchesSelector ||
            proto.oMatchesSelector || proto.webkitMatchesSelector;
    }
  
    function focusOnElement(el) {
      if (!el) {
        return;
      }
      function removeTI() {el.removeAttribute('tabindex');}
      if (!el.matches('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"]')) {
        // add tabindex to make focusable and remove again
        el.setAttribute('tabindex', -1);
        el.onblur = removeTI;
        el.onfocusout = removeTI;
      }
      el.focus();
    }
  
    if (document.location.hash) {
      let locid = document.location.hash.replace(/^#/,'');
      let elm = document.getElementById(locid);
      focusOnElement(elm);
    }
  
    // if the hash has been changed (activation of an in-page link)
    window.addEventListener('hashchange', function() {
      let id = window.location.hash.replace(/^#/,'');
      let el = document.getElementById(id);
      focusOnElement(el);
    });
  }

  manageInpageLinks();