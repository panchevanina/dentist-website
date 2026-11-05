'use strict';

document.documentElement.classList.add('js');

const header = document.querySelector('.site-header');
const menu = document.querySelector('.menu-toggle');
function closeMenu() {
  header?.classList.remove('nav-open');
  menu?.setAttribute('aria-expanded', 'false');
}
menu?.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  header.classList.toggle('nav-open', open);
});
document.querySelectorAll('#main-nav a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (header?.classList.contains('nav-open')) {
      closeMenu();
      menu.focus();
    }
  }
});
document.addEventListener('click', event => {
  if (!header?.contains(event.target)) closeMenu();
});
window.matchMedia('(min-width: 901px)').addEventListener('change', closeMenu);

const filterButtons = [...document.querySelectorAll('[data-filter]')];
const treatmentItems = [...document.querySelectorAll('.service-item, .treatment-article')];
const searchInput = document.querySelector('#treatment-search');
let currentCategory = 'all';
function filterTreatments() {
  const query = (searchInput?.value || '').trim().toLocaleLowerCase(document.documentElement.lang);
  let count = 0;
  treatmentItems.forEach(item => {
    const categoryMatches = currentCategory === 'all' || item.dataset.category === currentCategory;
    const queryMatches = !query || item.textContent.toLocaleLowerCase(document.documentElement.lang).includes(query);
    item.hidden = !(categoryMatches && queryMatches);
    if (!item.hidden) count++;
    if (item.id) {
      const link = document.querySelector(`[data-topic-link="${item.id}"]`);
      if (link) link.hidden = item.hidden;
    }
  });
  filterButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === currentCategory)));
  document.querySelectorAll('.featured-services-grid, .services-grid').forEach(group => {
    group.hidden = [...group.querySelectorAll('.service-item')].every(item => item.hidden);
  });
  const empty = document.querySelector('.no-results');
  if (empty) empty.hidden = count > 0;
}
filterButtons.forEach(button => button.addEventListener('click', () => {
  currentCategory = button.dataset.filter;
  filterTreatments();
}));
searchInput?.addEventListener('input', filterTreatments);
function openLinkedTreatment() {
  let hash;
  try { hash = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  if (!hash) return;
  if (hash.startsWith('category-')) {
    const category = hash.slice('category-'.length);
    if (filterButtons.some(button => button.dataset.filter === category)) {
      currentCategory = category;
      filterTreatments();
    }
    return;
  }
  const article = document.getElementById(hash);
  if (!article?.classList.contains('treatment-article')) return;
  currentCategory = 'all';
  if (searchInput) searchInput.value = '';
  filterTreatments();
  article.open = true;
  document.querySelectorAll('[data-topic-link]').forEach(link => {
    if (link.dataset.topicLink === hash) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  requestAnimationFrame(() => article.scrollIntoView({ block: 'start' }));
}
window.addEventListener('hashchange', openLinkedTreatment);
openLinkedTreatment();

// Image links remain ordinary, usable links when dialog support is unavailable.
const translations = document.body.dataset;
const lightbox = document.createElement('dialog');
lightbox.className = 'lightbox';
lightbox.setAttribute('aria-label', translations.image);
lightbox.innerHTML = '<div class="lightbox-inner"><div class="lightbox-toolbar"><span class="lightbox-count" aria-live="polite"></span><button type="button" class="lightbox-close">×</button></div><div class="lightbox-stage"><button type="button" class="lightbox-previous">←</button><div><img alt=""></div><button type="button" class="lightbox-next">→</button></div><p class="lightbox-caption"></p></div>';
lightbox.querySelector('.lightbox-close').setAttribute('aria-label', translations.close);
lightbox.querySelector('.lightbox-previous').setAttribute('aria-label', translations.previous);
lightbox.querySelector('.lightbox-next').setAttribute('aria-label', translations.next);
document.body.append(lightbox);
let images = [];
let imageIndex = 0;
let opener = null;
function showImage(index) {
  imageIndex = (index + images.length) % images.length;
  const anchor = images[imageIndex];
  const caption = anchor.getAttribute('aria-label') || anchor.querySelector('img')?.alt || translations.image;
  const image = lightbox.querySelector('img');
  image.src = anchor.href;
  image.alt = caption;
  lightbox.querySelector('.lightbox-caption').textContent = caption;
  lightbox.querySelector('.lightbox-count').textContent = `${imageIndex + 1} / ${images.length}`;
  lightbox.querySelectorAll('.lightbox-previous, .lightbox-next').forEach(button => { button.disabled = images.length < 2; });
}
document.addEventListener('click', event => {
  const anchor = event.target.closest('.zoom-image');
  if (!anchor || typeof lightbox.showModal !== 'function' || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  const group = anchor.closest('.photo-gallery, .article-body') || anchor.parentElement;
  images = [...group.querySelectorAll('.zoom-image')].filter(link => !link.closest('[hidden]'));
  if (!images.length) return;
  opener = anchor;
  showImage(images.indexOf(anchor));
  lightbox.showModal();
});
lightbox.querySelector('.lightbox-close').addEventListener('click', () => lightbox.close());
lightbox.querySelector('.lightbox-previous').addEventListener('click', () => showImage(imageIndex - 1));
lightbox.querySelector('.lightbox-next').addEventListener('click', () => showImage(imageIndex + 1));
lightbox.addEventListener('keydown', event => {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    showImage(imageIndex + (event.key === 'ArrowRight' ? 1 : -1));
  }
});
lightbox.addEventListener('close', () => {
  lightbox.querySelector('img').removeAttribute('src');
  opener?.focus({ preventScroll: true });
});
