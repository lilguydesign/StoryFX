import { escape } from './views.js';

const profileFields = [
  ['name','Nom du profil','Nom utilisé par les matrices. Un profil référencé ne peut pas être renommé directement.'],
  ['label','Nom affiché','Libellé lisible pour identifier le téléphone.'],
  ['enabled','Actif','Autorise ce profil dans la programmation. Décochez pour le désactiver.','checkbox'],
  ['device_id','Identifiant de connexion ADB','Adresse IP:port ou série Android. Modifier ce champ ne reconnecte pas ADB automatiquement.'],
  ['adb_serial','Numéro de série USB','Identité du téléphone déjà autorisé sur le PC. Le moteur refuse un matériel inconnu.'],
  ['tcpip_ip','Adresse IP Wi-Fi','Adresse du téléphone sur son réseau local. Le pilotage distant du PC passe toujours par HTTPS.'],
  ['tcpip_port','Port ADB Wi-Fi','Port configuré sur le téléphone ; 5555 par défaut. Aucun port n’est ouvert par cet écran.','number'],
  ['platform_version','Version Android','Version du système Android utilisée lors de la création de la session pilote.'],
  ['offset_minutes','Décalage en minutes','Décalage ajouté aux horaires des systèmes pour ce profil. Un changement suspend un scheduler déjà actif.','number'],
  ['appium_overrides','Options Appium (JSON)','Délais et options validés uniquement. Les options d’effacement et d’autorisation automatique sont refusées.','json'],
  ['gallery_package','Galerie · package Android','Exemple : com.sec.android.gallery3d. Le pilote actuel exige la galerie Samsung.'],
  ['gallery_activity','Galerie · activité Android','Écran de départ de la galerie ; exemple : com.sec.android.gallery3d.app.GalleryActivity.'],
];

export function profileForm(value) {
  const values = { ...value, gallery_package:value.gallery?.appPackage || '', gallery_activity:value.gallery?.appActivity || '' };
  return profileFields.map(([name,label,help,kind]) => {
    const current = values[name] ?? (kind === 'checkbox' ? true : name === 'tcpip_port' ? 5555 : name === 'offset_minutes' ? 0 : '');
    const input = kind === 'json' ? `<textarea name="${name}" rows="4">${escape(JSON.stringify(current || {},null,2))}</textarea>` :
      `<input name="${name}" type="${kind === 'checkbox' ? 'checkbox' : kind === 'number' ? 'number' : 'text'}" ${kind === 'checkbox' ? current ? 'checked' : '' : `value="${escape(current)}"`} ${name === 'name' ? 'required maxlength="80"' : ''} aria-describedby="profile-help-${name}">`;
    return `<label class="${kind === 'json' ? 'profile-wide' : ''}">${escape(label)}${input}<small id="profile-help-${name}" class="field-help">${escape(help)}</small>${name === 'adb_serial' ? '<button type="button" class="text-button" data-paste-serial>Coller le numéro de série</button>' : ''}</label>`;
  }).join('') + `<div class="profile-wide propagation-options"><label><input type="checkbox" name="propagate_device"> Propager connexion/IP/port aux profils qui utilisaient déjà le même téléphone</label><label><input type="checkbox" name="propagate_serial"> Propager le numéro de série aux mêmes profils</label><p class="helper">La propagation conserve leurs autres réglages. Le numéro de ligne et le nombre de matrices sont calculés.</p></div>`;
}

export function readProfile(form) {
  const value = {};
  for (const [name,,,kind] of profileFields) {
    const input = form.elements.namedItem(name);
    value[name] = kind === 'checkbox' ? input.checked : kind === 'number' ? Number(input.value) : kind === 'json' ? JSON.parse(input.value || '{}') : input.value.trim();
  }
  value.gallery = {appPackage:value.gallery_package,appActivity:value.gallery_activity};
  delete value.gallery_package; delete value.gallery_activity;
  return value;
}

let sortField = 'name', descending = false;
export function profilesTable(data, active) {
  const headings = [['enabled','Actif','Profil inclus dans la programmation'],['name','Nom','Nom utilisé dans les matrices'],
    ['device_id','Connexion ADB','Adresse ou identité de connexion'],['adb_serial','Série USB','Identité du téléphone autorisé'],
    ['tcpip_ip','IP Wi-Fi','Adresse locale du téléphone'],['tcpip_port','Port Wi-Fi','Port ADB configuré'],
    ['platform_version','Android','Version du système'],['offset_minutes','Décalage','Minutes ajoutées aux heures de base']];
  const rows = [...(data?.collections.profiles || [])].sort((a,b)=> {
    const x=a[sortField] ?? '', y=b[sortField] ?? '';
    const order = typeof x === 'number' && typeof y === 'number' ? x-y : String(x).localeCompare(String(y),'fr',{numeric:true});
    return descending ? -order : order;
  });
  const columns = [['name','Nom'],...headings.filter(([key])=>key !== 'name')];
  const options = columns.map(([key,label])=>`<option value="${key}" ${key === sortField ? 'selected' : ''}>${escape(label)}</option>`).join('');
  const toolbar = `<div class="control-filters"><label>Trier par<select data-profile-sort>${options}</select></label><label><input type="checkbox" data-profile-desc ${descending ? 'checked' : ''}> Ordre décroissant</label><button class="button secondary" data-control-refresh ${active ? '' : 'disabled'}>↻ Actualiser</button></div>`;
  const header = '<th title="Position calculée dans le tri actuel">Ligne</th>'+headings.map(([,label,help])=>`<th title="${escape(help)}">${escape(label)}</th>`).join('')+'<th title="Nombre de matrices utilisant ce profil">Matrices</th><th>Actions</th>';
  return toolbar+`<table><thead><tr>${header}</tr></thead><tbody>${rows.map((value,index)=>`<tr><td>${index+1}</td>${headings.map(([key])=>`<td>${escape(key === 'enabled' ? value[key] ? 'Oui' : 'Non' : value[key] ?? '')}</td>`).join('')}<td>${data.collections.matrix.filter(row=>row.device === value.name).length}</td><td><button class="text-button" data-setting="${value.id}" data-collection="profiles" ${active ? '' : 'disabled'}>Modifier</button><button class="text-button" data-profile-duplicate="${value.id}" ${active ? '' : 'disabled'}>Dupliquer</button></td></tr>`).join('')}</tbody></table>`;
}

export function changeProfileSort(event) {
  if (event.target.matches('[data-profile-sort]')) sortField=event.target.value;
  else if (event.target.matches('[data-profile-desc]')) descending=event.target.checked;
  else return false;
  return true;
}
