import { escape } from './views.js';
import { profileForm, readProfile } from './profile-editor.js';

export const controlTitles = {
  launch: 'Lancement', programming: 'Programmation', pages: 'Pages', profiles: 'Profils',
  systems: 'Systèmes', matrix: 'Matrices', albums: 'Albums', locators: 'Locators', reports: 'Rapports',
};
export const definitions = {
  profiles: [['name', 'Nom du profil'], ['label', 'Nom affiché'], ['enabled', 'Actif', 'checkbox'], ['offset_minutes', 'Décalage en minutes', 'number']],
  albums: [['name', 'Nom dans la galerie'], ['kind', 'Type'], ['album_size', 'Nombre d’images', 'number'], ['count_per_post', 'Images par publication', 'number']],
  systems: [['name', 'Nom du système'], ['times', 'Horaires HH:MM, séparés par des virgules', 'times']],
  pages: [['name', 'Nom de la page Facebook'], ['country', 'Pays']],
  matrix: [['name', 'Nom de la matrice'], ['enabled', 'Activer cette ligne : désactive seulement ce canal et ces albums', 'checkbox'], ['device', 'Profil', 'profiles'], ['platform', 'Plateforme', ['WhatsApp', 'Facebook', 'Instagram', 'TikTok']],
    ['system', 'Système', 'systems'], ['engine', 'Moteur', ['intro', 'multi', 'intro+multi']], ['album', 'Album introduction', 'albums'],
    ['album2', 'Album du lot multiple', 'albums'], ['count', 'Médias du lot multiple (introduction supplémentaire)', 'number'], ['page_name', 'Page Facebook', 'pages'], ['page', 'Pays']],
  locators: [['name', 'Nom du repère'], ['platform', 'Plateforme', ['WhatsApp', 'Facebook', 'Instagram', 'TikTok']], ['xpath', 'Sélecteur XPath']],
};
export const descriptions = {
  launch: 'Choisissez une occurrence de votre programmation. Un moteur Windows ou un agent Android compatible doit être prêt ; chaque occurrence ne peut partir qu’une fois.',
  programming: 'Horaires de la journée, calculés avec les décalages des profils. Fuseau : Africa/Douala. Le planning affiché ne démarre pas automatiquement.',
  pages: 'Vos pages par pays, sélectionnées dans les matrices Facebook.',
  profiles: 'Les noms historiques sont conservés. L’identité USB et les réglages réseau restent sur Windows.',
  systems: 'Les heures de base de vos systèmes, avant le décalage propre à chaque profil.',
  matrix: 'Introduction : une vidéo de l’album introduction. Multi : le nombre prévu dans l’album du lot. Intro + multi : une vidéo, puis le lot complet, au maximum 30 médias au total. Android 0.4.13 et les autorisations photos/vidéos sont requis pour ces modes WhatsApp. Facebook conserve ses matrices mais son adaptateur natif reste à construire.',
  albums: 'Créez les références des albums présents sur les téléphones. Le transfert des images vers les galeries viendra dans le dernier chantier.',
  locators: 'Repères utilisés pour retrouver des éléments de l’interface Android. Leur modification demande une nouvelle validation du moteur.',
  reports: 'Résultats des publications et état des agents Windows et Android. Un résultat incertain demande une vérification ; il ne repart pas automatiquement.',
};

export function fields(collection, value, catalog) {
  if (collection === 'profiles') return profileForm(value);
  return definitions[collection].map(([key, label, kind]) => {
    const current = value[key] ?? (kind === 'checkbox' ? true : kind === 'number' ? (key.includes('count') ? 1 : 0) : '');
    let input;
    if (kind === 'checkbox') input = `<input name="${key}" type="checkbox" ${current ? 'checked' : ''}>`;
    else if (Array.isArray(kind) || catalog[kind]) {
      const options = Array.isArray(kind) ? kind : catalog[kind].map(item => item.name);
      if (current && !options.includes(current)) options.push(current);
      input = `<select name="${key}">${['', ...options].map(option => `<option value="${escape(option)}" ${option === current ? 'selected' : ''}>${escape(option || '—')}</option>`).join('')}</select>`;
    } else input = `<input name="${key}" type="${kind === 'number' ? 'number' : 'text'}" value="${escape(kind === 'times' ? (current || []).join(', ') : current)}" ${key === 'name' ? 'required maxlength="80"' : ''}>`;
    return `<label>${escape(label)}${input}</label>`;
  }).join('');
}

export function readFields(collection, form) {
  if (collection === 'profiles') return readProfile(form);
  return Object.fromEntries(definitions[collection].map(([key, , kind]) => {
    const input = form.elements.namedItem(key);
    const value = kind === 'checkbox' ? input.checked : kind === 'number' ? Number(input.value) :
      kind === 'times' ? input.value.split(',').map(text => text.trim()).filter(Boolean) : input.value.trim();
    return [key, value];
  }));
}
