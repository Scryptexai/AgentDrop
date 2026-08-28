const switchToPopupTab = (event) => {
  window.removeEventListener('beforeunload', switchToPopupTab);
  if (!event) {
    chrome.tabs.query(
      {
        currentWindow: true,
        active: true,
      },
      (current) => {
        if (!current.length) {
          return;
        }
        chrome.tabs.query(
          {
            index: current[0].index - 1,
          },
          (popup) => {
            if (!popup.length) {
              return;
            }
            chrome.tabs.update(popup[0].id, { active: true });
          }
        );
        chrome.tabs.remove(current[0].id);
      }
    );
    return;
  }

  chrome.tabs.query(
    {
      url: '*://connect.trezor.io/*/popup.html',
    },
    (tabs) => {
      if (!tabs.length) {
        return;
      }
      chrome.tabs.update(tabs[0].id, { active: true });
    }
  );
};

window.addEventListener('message', (event) => {
  if (event.data === 'usb-permissions-init') {
    const iframe = document.getElementById('trezor-usb-permissions');
    iframe.contentWindow.postMessage(
      {
        type: 'usb-permissions-init',
        extension: chrome.runtime.id,
      },
      '*'
    );
  } else if (event.data === 'usb-permissions-close') {
    switchToPopupTab(null);
  }
});

window.addEventListener('beforeunload', switchToPopupTab);

window.addEventListener('load', () => {
  const instance = document.createElement('iframe');
  instance.id = 'trezor-usb-permissions';
  instance.width = '100%';
  instance.height = '100%';
  instance.style.border = '0px';
  instance.style.width = '100%';
  instance.style.height = '100%';
  instance.setAttribute(
    'src',
    'https://connect.trezor.io/9/extension-permissions.html'
  );
  instance.setAttribute('allow', 'usb');

  if (document.body) {
    document.body.appendChild(instance);
  }
});
