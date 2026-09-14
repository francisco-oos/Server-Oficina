/*
 * Server Oficina · interfaz web
 * =============================
 *
 * Arquitectura de la interfaz
 * ---------------------------
 * Aplicación de una sola página, sin framework ni dependencias remotas: el
 * servidor de la Latitude sirve la LAN y no debe depender de una CDN.
 *
 * Tres ideas gobiernan este archivo:
 *
 * 1. NAVEGACIÓN DOBLE. Por área en la barra lateral (RRHH trabaja desde RRHH,
 *    Transporte desde Transporte) y transversal mediante el buscador de la
 *    cabecera. Ambas son necesarias; ninguna sustituye a la otra.
 *
 * 2. LA FICHA DEPENDE DEL DOMINIO. Tracking Core es común por debajo, pero una
 *    persona, un nodo, un radio y una unidad de transporte NO se muestran
 *    igual. Cada una tiene su propio renderizador (renderPersona, renderNodo,
 *    renderActivo, renderUnidad) y el backend indica cuál corresponde.
 *
 * 3. NO TODO ES UNA TABLA. Donde aporta, se usa resumen, ficha, timeline,
 *    estado actual, alertas, relaciones y acciones contextuales. Las tablas se
 *    reservan para listados que realmente se leen como tabla.
 *
 * Convención de permisos: la interfaz oculta lo que el usuario no puede hacer,
 * pero eso es ergonomía, no seguridad. La autorización real la impone el
 * backend en cada endpoint.
 */

'use strict';

// --- Utilidades base ---------------------------------------------------------

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** Estado de sesión y contexto operativo (áreas, permisos, dominios). */
let ME = null;
let CONTEXT = null;

/** Escapa texto antes de inyectarlo en HTML. Se usa SIEMPRE con datos del servidor. */
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));

const can = permission => !!ME?.permissions?.includes(permission);

/** Fecha y hora legibles; los nulos se muestran como guion, nunca como "null". */
const fmt = value => (value ? new Date(value).toLocaleString('es-MX', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
}) : '—');

const fmtDate = value => (value ? new Date(value).toLocaleDateString('es-MX', {
  day: '2-digit', month: '2-digit', year: 'numeric'
}) : '—');

const badge = (value, kind = '') => `<span class="badge ${kind}">${esc(value || '—')}</span>`;

/** Valor de ficha: distingue "no capturado" de un valor vacío real. */
const field = (label, value, extra = '') =>
  `<div class="field"><span class="field-label">${esc(label)}</span>
   <span class="field-value ${value ? '' : 'missing'}">${value ? esc(value) : 'No capturado'}${extra}</span></div>`;

/**
 * Convierte el cuerpo de un error de FastAPI en texto legible.
 * Existe porque `detail` puede ser una cadena o una lista de errores de
 * validación de Pydantic; sin esto la interfaz mostraba "[object Object]".
 */
function errorText(body, status) {
  const d = body?.detail ?? body;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map(x => {
      const campo = Array.isArray(x.loc) ? x.loc.filter(p => p !== 'body').join('.') : '';
      return campo ? `${campo}: ${x.msg}` : x.msg;
    }).join(' · ');
  }
  if (d && typeof d === 'object') return JSON.stringify(d);
  return `Error ${status}`;
}

/**
 * Cliente HTTP único. Serializa JSON salvo cuando se envía FormData (subida de
 * archivos), y convierte cualquier respuesta no exitosa en una excepción con
 * mensaje ya legible para el operador.
 */
async function api(url, options = {}) {
  const init = { method: options.method || 'GET', headers: {}, credentials: 'same-origin' };
  if (options.body instanceof FormData) {
    init.body = options.body;
  } else if (options.body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(options.body);
  }
  const response = await fetch(url, init);
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!response.ok) throw new Error(errorText(data, response.status));
  return data;
}

function show(id) {
  ['setup', 'login', 'app'].forEach(x => $('#' + x).classList.toggle('hidden', x !== id));
}

function setTitle(title, eyebrow = 'CONTROL OPERATIVO') {
  $('#title').textContent = title;
  $('#eyebrow').textContent = eyebrow;
}

function msg(form, text, ok = false) {
  const node = form.querySelector('.msg');
  if (node) { node.textContent = text; node.classList.toggle('ok', ok); }
}

function showError(error) {
  $('#content').innerHTML = `<div class="panel empty-state">
    <h3>No se pudo cargar</h3>
    <p class="muted">${esc(error.message)}</p>
  </div>`;
}

/** Panel vacío con mensaje explícito, en lugar de una tabla sin filas. */
const emptyState = text => `<div class="empty">${esc(text)}</div>`;

/** Envuelve una tabla para que en pantallas estrechas haga scroll horizontal
 *  ella sola, sin arrastrar el resto de la página. */
const table = (headers, rows) => rows.length
  ? `<div class="tablewrap"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
     <tbody>${rows.join('')}</tbody></table></div>`
  : emptyState('Sin registros');

/** Línea de tiempo. Muestra siempre ocurrió y se registró por separado. */
function timeline(events) {
  if (!events?.length) return emptyState('Sin eventos registrados');
  return `<ol class="timeline">${events.map(e => `
    <li>
      <div class="tl-dot"></div>
      <div class="tl-body">
        <strong>${esc(e.event_type || e.movement_type || e.operation_type || 'Evento')}</strong>
        <div class="tl-meta">
          <span title="Fecha en que ocurrió en campo">Ocurrió: ${fmt(e.occurred_at)}</span>
          <span title="Fecha en que se capturó en el sistema">Registrado: ${fmt(e.recorded_at)}</span>
          ${e.source_type ? `<span>Fuente: ${esc(e.source_type)}</span>` : ''}
        </div>
        ${e.note ? `<div class="tl-note">${esc(e.note)}</div>` : ''}
        ${e.payload && Object.keys(e.payload).length
          ? `<div class="tl-payload">${Object.entries(e.payload)
              .filter(([, v]) => v !== null && v !== undefined && v !== '')
              .map(([k, v]) => `<span><b>${esc(k)}</b> ${esc(typeof v === 'object' ? JSON.stringify(v) : v)}</span>`).join('')}</div>`
          : ''}
      </div>
    </li>`).join('')}</ol>`;
}

// --- Modelo de navegación por área ------------------------------------------
/*
 * El menú se declara aquí como datos, no como HTML fijo. Cada entrada indica el
 * área a la que pertenece y el permiso que la habilita; el menú real se
 * construye filtrando por los permisos del usuario que inició sesión.
 *
 * Agregar un módulo nuevo es agregar una fila a esta tabla y registrar su vista
 * en VIEWS. No hace falta tocar index.html.
 */
const NAV = [
  { area: 'RESUMEN', label: 'Vista resumen', icon: '▦', view: 'resumen', permission: 'dashboard.view' },

  { area: 'RRHH', label: 'Personal', icon: '♙', view: 'people', permission: 'person.view' },
  { area: 'RRHH', label: 'Asistencia', icon: '◷', view: 'attendance', permission: 'attendance.manage' },
  { area: 'RRHH', label: 'EPP', icon: '◇', view: 'epp', permission: 'epp.view' },
  { area: 'RRHH', label: 'Importaciones', icon: '⇧', view: 'imports', permission: 'attendance.import' },

  { area: 'HSE', label: 'Capacitación', icon: '△', view: 'training', permission: 'training.view' },
  { area: 'HSE', label: 'Incidencias y casos', icon: '!', view: 'cases', permission: 'cases.create' },

  { area: 'TRANSPORTE', label: 'Unidades', icon: '⛟', view: 'transport', permission: 'transport.view' },
  { area: 'TRANSPORTE', label: 'Checklist', icon: '☑', view: 'checklists', permission: 'transport.view' },
  { area: 'TRANSPORTE', label: 'Incidencias de unidad', icon: '⚠', view: 'transportIncidents', permission: 'transport.view' },

  { area: 'MATERIAL', label: 'Activos y material', icon: '▣', view: 'assets', permission: 'assets.view' },
  { area: 'MATERIAL', label: 'Inventario físico', icon: '✓', view: 'inventory', permission: 'assets.view' },
  { area: 'MATERIAL', label: 'Evidencias', icon: '⬆', view: 'evidence', permission: 'evidence.view' },
  { area: 'MATERIAL', label: 'Cierre de proyecto', icon: '⊘', view: 'closeout', permission: 'inventory.closeout' },

  { area: 'OPERACION', label: 'Tracking Nodes', icon: '⌁', view: 'nodes', permission: 'nodes.view' },

  { area: 'TALLER', label: 'Órdenes de taller', icon: '⚙', view: 'maintenance', permission: 'maintenance.view' },

  { area: 'ADMIN', label: 'Proyectos y ubicaciones', icon: '▤', view: 'projects', permission: 'projects.manage' },
  { area: 'ADMIN', label: 'Perfiles y permisos', icon: '⌘', view: 'roles', permission: 'roles.manage' },
  { area: 'ADMIN', label: 'Autoridad del dato', icon: '⚖', view: 'authority', permission: 'dashboard.view' },
  { area: 'ADMIN', label: 'Catálogos', icon: '☷', view: 'catalogs', permission: 'catalogs.manage' },
  { area: 'ADMIN', label: 'Usuarios', icon: '♧', view: 'users', permission: 'users.manage', id: 'usersNav' },
  { area: 'ADMIN', label: 'Modo DEV · Dashboard', icon: '⚡', view: 'devDashboard', permission: 'dashboard.configure' },
  { area: 'ADMIN', label: 'Auditoría', icon: '≡', view: 'audit', permission: 'audit.view' }
];

/** Rótulos de los grupos del menú. Coinciden con las áreas del backend. */
const AREA_LABELS = {
  RESUMEN: 'RESUMEN',
  RRHH: 'RECURSOS HUMANOS',
  HSE: 'SEGURIDAD / HSE',
  TRANSPORTE: 'TRANSPORTE',
  MATERIAL: 'CONTROL DE MATERIAL',
  OPERACION: 'OPERACIÓN · NODOS',
  TALLER: 'TALLER / TX',
  ADMIN: 'ADMINISTRACIÓN'
};

/**
 * Construye el menú lateral con las entradas que el usuario puede usar.
 * Las áreas propias del usuario se marcan para que encuentre su trabajo primero,
 * sin ocultarle el resto: el sistema es compartido por diseño.
 */
function buildNav() {
  const myAreas = new Set((CONTEXT?.areas || []).map(a => a.code));
  const groups = new Map();
  for (const item of NAV) {
    if (!can(item.permission)) continue;
    if (!groups.has(item.area)) groups.set(item.area, []);
    groups.get(item.area).push(item);
  }
  $('#nav').innerHTML = [...groups.entries()].map(([area, items]) => `
    <div class="nav-group ${myAreas.has(area) ? 'own-area' : ''}">
      <span>${esc(AREA_LABELS[area] || area)}${myAreas.has(area) ? ' <em>· tu área</em>' : ''}</span>
      ${items.map(i => `<button data-view="${i.view}"${i.id ? ` id="${i.id}"` : ''}>
        <span class="nav-icon">${i.icon}</span>${esc(i.label)}</button>`).join('')}
    </div>`).join('');
  $$('#nav button').forEach(b => b.onclick = () => { closeMenu(); navigate(b.dataset.view); });
}

// --- Enrutado ---------------------------------------------------------------

/** Vista actual, para que las fichas puedan volver atrás con contexto. */
let CURRENT = { view: 'resumen', params: {} };

function navigate(view, params = {}) {
  CURRENT = { view, params };
  $$('#nav button').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  const handler = VIEWS[view];
  if (!handler) return showError(new Error(`Vista desconocida: ${view}`));
  $('#content').innerHTML = '<div class="loading">Cargando…</div>';
  Promise.resolve(handler(params)).catch(showError);
}

/**
 * Enlaza los elementos que llevan a una ficha. Un solo punto de entrada evita
 * que cada vista invente su propia forma de navegar entre entidades.
 */
function bindLinks(root = document) {
  $$('[data-goto]', root).forEach(el => {
    el.onclick = event => {
      event.preventDefault();
      navigate(el.dataset.goto, { id: el.dataset.id });
    };
  });
}

/** Traduce el "link" que sugiere un widget del backend a una vista de la UI. */
function widgetLink(link) {
  if (!link) return null;
  const map = {
    people: 'people', person: 'person', assets: 'assets', asset: 'asset', node: 'node',
    attendance: 'attendance', epp: 'epp', training: 'training', cases: 'cases',
    maintenance: 'maintenance', inventory: 'inventory', transport: 'transport',
    'transport-unit': 'transportUnit', evidence: 'evidence'
  };
  const view = map[link.view];
  return view ? { view, params: link.params || {} } : null;
}

// --- Menú responsive ---------------------------------------------------------
// En tableta y teléfono la barra lateral se oculta y se abre como panel. En
// escritorio permanece fija: son dos modos, no un menú que estorba en ambos.

function openMenu() {
  $('#sidebar').classList.add('open');
  $('#scrim').classList.remove('hidden');
  $('#menuToggle').setAttribute('aria-expanded', 'true');
}

function closeMenu() {
  $('#sidebar').classList.remove('open');
  $('#scrim').classList.add('hidden');
  $('#menuToggle').setAttribute('aria-expanded', 'false');
}

// --- Vista resumen configurable ---------------------------------------------
/*
 * La pantalla principal ya no es una colección fija de contadores. El backend
 * devuelve los widgets que el administrador configuró para este dashboard, ya
 * filtrados por los permisos del usuario, y aquí sólo se dibujan según su tipo.
 *
 * Agregar un widget nuevo en el backend NO requiere tocar este archivo: si su
 * "kind" es uno de los cuatro conocidos, se dibuja solo.
 */

const TONE_CLASS = { ok: 'ok', warn: 'warn', bad: 'bad', neutral: '' };

function renderWidget(card) {
  if (!card.ok) {
    return `<article class="widget size-${esc(card.size)} widget-error">
      <h3>${esc(card.title)}</h3>
      <p class="muted small">${esc(card.error || 'No disponible')}</p>
    </article>`;
  }
  const data = card.data || {};
  let body = '';
  if (card.kind === 'METRIC') {
    body = `<div class="metric-value ${TONE_CLASS[data.tone] || ''}">${esc(data.value)}</div>
            <div class="metric-hint">${esc(data.hint || '')}</div>`;
  } else if (card.kind === 'BREAKDOWN') {
    body = data.rows?.length
      ? `<ul class="breakdown">${data.rows.map(r => `<li class="${TONE_CLASS[r.tone] || ''}">
          <span>${esc(r.label)}</span><b>${esc(r.value)}</b></li>`).join('')}</ul>`
      : emptyState(data.empty || 'Sin datos');
  } else { // LIST y ALERT comparten presentación; ALERT sólo cambia el acento.
    body = data.items?.length
      ? `<ul class="widget-list">${data.items.map(item => {
          const target = widgetLink(item.link);
          const attrs = target ? ` data-goto="${esc(target.view)}" data-id="${esc(target.params.id || '')}" class="linkable ${TONE_CLASS[item.tone] || ''}"` : ` class="${TONE_CLASS[item.tone] || ''}"`;
          return `<li${attrs}>
            <span class="wl-primary">${esc(item.primary)}</span>
            <span class="wl-secondary">${esc(item.secondary || '')}</span>
            <span class="wl-meta">${esc(item.meta || '')}</span>
          </li>`;
        }).join('')}</ul>`
      : emptyState(data.empty || 'Sin pendientes');
  }
  const target = widgetLink(data.link);
  return `<article class="widget size-${esc(card.size)} kind-${esc(card.kind.toLowerCase())}"
            ${target ? `data-goto="${esc(target.view)}" data-id="${esc(target.params.id || '')}"` : ''}>
    <h3 title="${esc(card.description || '')}">${esc(card.title)}</h3>
    ${body}
  </article>`;
}

async function resumen(params = {}) {
  const dashboards = await api('/api/dashboards');
  if (!dashboards.length) {
    setTitle('Vista resumen');
    $('#content').innerHTML = emptyState('No hay vistas resumen configuradas.');
    return;
  }
  const key = params.key || CURRENT.params.key || dashboards.find(d => d.own_area)?.key || dashboards[0].key;
  const payload = await api('/api/dashboards/' + encodeURIComponent(key));
  const info = payload.dashboard;
  setTitle(info.name, 'VISTA RESUMEN');

  $('#content').innerHTML = `
    <div class="dashboard-switch">
      ${dashboards.map(d => `<button class="chip ${d.key === key ? 'active' : ''}" data-dash="${esc(d.key)}">
        ${esc(d.name)}${d.own_area ? ' ·' : ''}</button>`).join('')}
    </div>
    <p class="muted view-hint">${esc(info.description || '')}</p>
    ${payload.widgets.length
      ? `<div class="widget-grid">${payload.widgets.map(renderWidget).join('')}</div>`
      : `<div class="panel empty-state"><h3>Esta vista resumen está vacía</h3>
         <p class="muted">${can('dashboard.configure')
            ? 'Configúrela desde Administración › Modo DEV · Dashboard.'
            : 'Solicite a un administrador que configure los indicadores de su área.'}</p></div>`}`;

  $$('[data-dash]').forEach(b => b.onclick = () => navigate('resumen', { key: b.dataset.dash }));
  bindLinks();
}

// --- Búsqueda transversal ----------------------------------------------------

/** Etiqueta y vista destino de cada tipo de ficha que devuelve la búsqueda. */
const DOSSIER_VIEW = {
  person: { view: 'person', label: 'Persona', icon: '♙' },
  node: { view: 'node', label: 'Nodo', icon: '⌁' },
  asset: { view: 'asset', label: 'Activo', icon: '▣' },
  'transport-unit': { view: 'transportUnit', label: 'Unidad', icon: '⛟' }
};

async function buscar(params = {}) {
  const term = params.q ?? $('#globalSearchInput').value ?? '';
  setTitle('Resultados de búsqueda', 'BÚSQUEDA TRANSVERSAL');
  if (term.trim().length < 2) {
    $('#content').innerHTML = `<div class="panel empty-state"><h3>Escriba al menos 2 caracteres</h3>
      <p class="muted">Puede buscar por nombre, ID laboral, número de serie, IMEI, QR o número económico.</p></div>`;
    return;
  }
  const payload = await api('/api/search?q=' + encodeURIComponent(term.trim()));
  $('#content').innerHTML = `
    <div class="panel">
      <div class="panel-head">
        <h3>“${esc(payload.query)}”</h3>
        <span class="muted small">${payload.count} resultado(s)${
          payload.hidden_by_permissions ? ` · ${payload.hidden_by_permissions} oculto(s) por permisos` : ''}</span>
      </div>
      ${payload.results.length ? `<div class="result-list">${payload.results.map(r => {
        const meta = DOSSIER_VIEW[r.dossier] || { view: 'asset', label: r.dossier, icon: '▪' };
        return `<button class="result" data-goto="${meta.view}" data-id="${esc(r.id)}">
          <span class="result-icon">${meta.icon}</span>
          <span class="result-main">
            <strong>${esc(r.label)}</strong>
            <span class="muted small">${esc(r.sublabel || '')}</span>
          </span>
          <span class="result-side">
            ${badge(meta.label)}
            ${badge(r.status, TONE_CLASS[r.tone] || '')}
            <span class="muted small">coincide por ${esc(r.matched_on)}</span>
          </span>
        </button>`;
      }).join('')}</div>` : emptyState('Sin coincidencias. Verifique el término o pruebe con la serie completa.')}
    </div>
    ${payload.hidden_by_permissions ? `<p class="muted small note">
      Se encontraron ${payload.hidden_by_permissions} coincidencia(s) en áreas para las que su perfil no tiene
      permiso de consulta. Solicite acceso al área correspondiente si necesita verlas.</p>` : ''}`;
  bindLinks();
}

// --- Fichas por dominio ------------------------------------------------------
/*
 * Aquí vive la regla central del encargo: todo tiene trazabilidad, pero NO todo
 * tiene la misma interfaz. Las cuatro fichas comparten el mismo lenguaje visual
 * (resumen arriba, pestañas de secciones, timeline al final) y ninguna comparte
 * contenido con otra, porque sus dominios no son intercambiables.
 */

/** Cabecera de ficha: resumen y acciones contextuales. */
function dossierHeader({ eyebrow, title, subtitle, chips = [], actions = '' }) {
  return `<div class="dossier-head">
    <div>
      <div class="eyebrow">${esc(eyebrow)}</div>
      <h2>${esc(title)}</h2>
      <div class="muted">${esc(subtitle || '')}</div>
      <div class="chips">${chips.map(c => badge(c.text, c.tone || '')).join('')}</div>
    </div>
    <div class="dossier-actions">${actions}</div>
  </div>`;
}

/**
 * Pestañas de secciones. Se usan en vez de apilar diez tablas una tras otra:
 * un expediente completo no cabe legible en una sola columna, y obligar a
 * recorrer toda la página para llegar al historial es un mal flujo cotidiano.
 */
function tabs(sections) {
  const available = sections.filter(s => s.body);
  if (!available.length) return '';
  return `<div class="tabs" role="tablist">
      ${available.map((s, i) => `<button role="tab" class="tab ${i === 0 ? 'active' : ''}"
        data-tab="${esc(s.key)}">${esc(s.label)}${s.count !== undefined ? ` <em>${s.count}</em>` : ''}</button>`).join('')}
    </div>
    ${available.map((s, i) => `<div class="tab-panel ${i === 0 ? '' : 'hidden'}" data-panel="${esc(s.key)}">${s.body}</div>`).join('')}`;
}

function bindTabs(root = document) {
  $$('.tab', root).forEach(btn => btn.onclick = () => {
    $$('.tab', root).forEach(b => b.classList.toggle('active', b === btn));
    $$('.tab-panel', root).forEach(p => p.classList.toggle('hidden', p.dataset.panel !== btn.dataset.tab));
  });
}

// --- Ficha de PERSONA --------------------------------------------------------

async function person(params) {
  const id = params.id;
  const d = await api('/api/dossier/person/' + encodeURIComponent(id));
  const s = d.summary;
  setTitle(s.full_name, 'EXPEDIENTE DE PERSONAL');

  /*
   * Bloque de localización rápida que pide el encargo. Se muestran los campos
   * aunque falten: distinguir "no capturado" de "vacío" le dice al usuario de
   * RRHH qué información hace falta recoger.
   */
  const resumenBlock = `<div class="panel summary-card">
    <div class="panel-head"><h3>Localización</h3>${badge(s.estado, s.estado === 'Activo' ? 'ok' : 'warn')}</div>
    <div class="field-grid">
      ${field('Grupo', s.grupo)}
      ${field('Responsable / supervisor', s.responsable)}
      ${field('Unidad', s.unidad, s.unidad_asset_id
          ? ` <a class="inline-link" data-goto="transportUnit" data-id="${esc(s.unidad_asset_id)}">ver unidad</a>` : '')}
      ${field('Conductor', s.conductor, s.es_conductor ? ' <span class="tag">es esta persona</span>' : '')}
      ${field('Radio', s.radio)}
      ${field('Teléfono', s.telefono)}
      ${field('Ubicación / campamento', s.ubicacion)}
      ${field('Proyecto', s.proyecto)}
      ${field('ID laboral vigente', s.employment_id)}
      ${field('Puesto', s.puesto)}
      ${field('Categoría', s.categoria)}
    </div>
  </div>`;

  const hr = d.hr_profile;
  const hrBlock = hr ? `<div class="panel">
    <h3>Datos laborales</h3>
    <div class="field-grid">
      ${field('Categoría', hr.category)}
      ${field('Licencia', hr.license_number ? `${hr.license_type || ''} ${hr.license_number}`.trim() : null,
        hr.license_expired ? ' <span class="tag bad">vencida</span>' : '')}
      ${field('Vigencia de licencia', hr.license_expiry ? fmtDate(hr.license_expiry) : null)}
      ${field('Rotación trabajo/descanso',
        hr.rotation_on_days ? `${hr.rotation_on_days} × ${hr.rotation_off_days ?? '—'} días` : null)}
      ${field('Teléfono', hr.phone)}
      ${field('Contacto de emergencia', hr.emergency_contact)}
    </div>
  </div>` : `<div class="panel">${emptyState('Sin ficha laboral capturada todavía.')}</div>`;

  /*
   * Historia laboral. Cada contratación se muestra como bloque propio porque
   * persona ≠ contratación: una recontratación es una relación nueva sobre la
   * MISMA identidad, y el expediente debe dejarlo ver.
   */
  const historia = d.engagements.length ? d.engagements.map(e => `
    <div class="engagement">
      <div class="engagement-head">
        <strong>${esc(e.employment_id)}</strong>
        ${badge(e.status, e.end_date ? 'warn' : 'ok')}
        <span class="muted small">${fmtDate(e.start_date)} → ${e.end_date ? fmtDate(e.end_date) : 'vigente'}</span>
      </div>
      <div class="field-grid compact">
        ${field('Puesto', e.position)}
        ${field('Tipo de empleador', e.employer_type)}
        ${field('Empresa / outsourcing',
          e.organizations.map(o => o.name).join(', ') || e.provider)}
        ${field('Proyecto', e.project)}
      </div>
      ${e.contract_periods.length ? `<div class="subsection"><h4>Contratos y renovaciones</h4>
        ${table(['Inicio', 'Fin', 'Fuente'], e.contract_periods.map(c =>
          `<tr><td>${fmtDate(c.start_date)}</td><td>${c.end_date ? fmtDate(c.end_date) : '—'}</td><td>${esc(c.source || '—')}</td></tr>`))}
      </div>` : ''}
      ${e.lifecycle.length ? `<div class="subsection"><h4>Eventos laborales</h4>
        ${table(['Evento', 'Fecha', 'Motivo'], e.lifecycle.map(x =>
          `<tr><td>${badge(x.event_type)}</td><td>${fmtDate(x.occurred_on)}</td><td>${esc(x.reason || '—')}</td></tr>`))}
      </div>` : ''}
    </div>`).join('') : emptyState('Sin relaciones laborales registradas');

  const secciones = tabs([
    { key: 'historia', label: 'Historia laboral', count: d.engagements.length, body: historia },
    { key: 'asignaciones', label: 'Asignaciones', count: d.assignments.length,
      body: table(['Proyecto', 'Grupo', 'Ubicación', 'Supervisor', 'Unidad', 'Desde', 'Hasta'],
        d.assignments.map(a => `<tr class="${a.current ? 'row-current' : ''}">
          <td>${esc(a.project || '—')}</td><td>${esc(a.group || '—')}</td><td>${esc(a.location || '—')}</td>
          <td>${esc(a.supervisor || '—')}</td><td>${esc(a.unit || '—')}</td>
          <td>${fmt(a.start_at)}</td><td>${a.end_at ? fmt(a.end_at) : badge('vigente', 'ok')}</td></tr>`)) },
    { key: 'asistencia', label: 'Asistencia', count: d.attendance.length,
      body: table(['Fecha', 'Estado', 'Origen'], d.attendance.map(a =>
        `<tr><td>${fmtDate(a.date)}</td><td>${badge(a.status)}</td>
         <td>${a.imported ? 'Importada' : 'Captura manual'}</td></tr>`)) },
    { key: 'cursos', label: 'Cursos', count: d.training.length,
      body: table(['Curso', 'Estado', 'Programado', 'Completado'], d.training.map(t =>
        `<tr><td>${esc(t.course)}</td><td>${badge(t.state, t.state === 'COMPLETED' ? 'ok' : 'warn')}</td>
         <td>${t.scheduled_for ? fmtDate(t.scheduled_for) : '—'}</td><td>${fmt(t.completed_at)}</td></tr>`)) },
    { key: 'epp', label: 'EPP', count: d.epp.length,
      body: table(['Artículo', 'Motivo', 'Estado', 'Solicitado', 'Resolución'], d.epp.map(e =>
        `<tr><td>${esc(e.item_type)}</td><td>${esc(e.reason)}</td>
         <td>${badge(e.status, e.status === 'APPROVED' ? 'ok' : e.status === 'PENDING' ? 'warn' : '')}</td>
         <td>${fmt(e.requested_at)}</td><td>${esc(e.review_note || '—')}</td></tr>`)) },
    { key: 'activos', label: 'Activos entregados', count: d.assets_current.length,
      body: `${d.assets_current.length ? `<h4>En custodia actual</h4>${table(['Activo', 'Tipo', 'Estado', ''],
        d.assets_current.map(a => `<tr><td>${esc(a.label)}</td><td>${esc(a.type || '—')}</td><td>${badge(a.status)}</td>
          <td><button class="link" data-goto="${a.dossier === 'node' ? 'node' : a.dossier === 'transport-unit' ? 'transportUnit' : 'asset'}"
            data-id="${esc(a.id)}">abrir ficha</button></td></tr>`))}` : emptyState('Sin activos en custodia actual')}
        <h4>Historial de entregas y devoluciones</h4>
        ${table(['Activo', 'Tipo de entrega', 'Desde', 'Hasta', 'Nota'], d.assets_history.map(h =>
          `<tr><td>${esc(h.label)}</td><td>${esc(h.assignment_type)}</td><td>${fmt(h.start_at)}</td>
           <td>${h.returned ? fmt(h.end_at) : badge('sin devolver', 'warn')}</td><td>${esc(h.note || '—')}</td></tr>`))}` },
    { key: 'casos', label: 'Casos e incidencias', count: d.cases.length,
      body: `<p class="muted small note">Los casos registran <b>hechos observados</b> y su evidencia.
        No constituyen una sanción: el área competente es quien resuelve.</p>
        ${table(['Tipo', 'Resumen', 'Estado', 'Reportado', 'Resolución'], d.cases.map(c =>
          `<tr><td>${esc(c.case_type)}</td><td>${esc(c.summary)}</td>
           <td>${badge(c.status, c.status === 'OPEN' ? 'warn' : 'ok')}</td>
           <td>${fmt(c.reported_at)}</td><td>${esc(c.resolution || '—')}</td></tr>`))}` },
    { key: 'nodos', label: 'Nodos relacionados', count: d.node_exceptions.length,
      body: d.node_exceptions.length ? `<p class="muted small note">Excepciones de nodos en las que esta persona figura
          como responsable del registro. Es un dato de trazabilidad, no una imputación.</p>
        ${table(['Nodo', 'Resultado', 'Estado resultante', 'Operación', 'Fecha', ''], d.node_exceptions.map(n =>
          `<tr><td>${esc(n.asset_label)}</td><td>${badge(n.result_code, 'bad')}</td>
           <td>${badge(n.new_status_code || '—')}</td><td>${esc(n.operation_type || '—')}</td><td>${fmt(n.occurred_at)}</td>
           <td><button class="link" data-goto="node" data-id="${esc(n.asset_id)}">ver nodo</button></td></tr>`))}`
        : emptyState('Sin nodos con excepción asociados a esta persona') },
    { key: 'evidencias', label: 'Evidencias', count: d.evidence.length,
      body: table(['Archivo', 'Origen', 'SHA-256', 'Registrada'], d.evidence.map(e =>
        `<tr><td>${esc(e.name)}</td><td>${esc(e.source)}</td>
         <td class="code">${esc(String(e.sha256).slice(0, 16))}…</td><td>${fmt(e.created_at)}</td></tr>`)) },
    { key: 'timeline', label: 'Historial completo', count: d.timeline.length, body: timeline(d.timeline) }
  ]);

  $('#content').innerHTML = `
    ${dossierHeader({
      eyebrow: 'PERSONA · IDENTIDAD ESTABLE',
      title: s.full_name,
      subtitle: `${s.puesto || 'Sin puesto capturado'} · ${s.proyecto || 'Sin proyecto'}`,
      chips: [
        { text: s.estado, tone: s.estado === 'Activo' ? 'ok' : 'warn' },
        { text: s.grupo || 'Sin grupo' },
        { text: s.ubicacion || 'Sin ubicación' }
      ],
      actions: `<button class="secondary" data-back>← Volver a Personal</button>`
    })}
    ${resumenBlock}
    ${hrBlock}
    <div class="panel">${secciones}</div>`;
  bindTabs();
  bindLinks();
  $('[data-back]').onclick = () => navigate('people');
}

// --- Cabecera común de activo ------------------------------------------------
/*
 * Lo único que las tres fichas de activo comparten: identidad, tipo y
 * ubicación. Todo lo demás cambia por dominio.
 */
function assetIdentityPanel(h) {
  const ids = h.identifiers || [];
  return `<div class="panel summary-card">
    <div class="panel-head"><h3>Identidad</h3>${badge(h.status_code, h.active ? '' : 'warn')}</div>
    <div class="field-grid">
      ${field('Tipo', h.type_name)}
      ${field('Tecnología / fabricante', h.technology ? `${h.technology}${h.vendor ? ` · ${h.vendor}` : ''}` : null)}
      ${field('Número interno / económico', h.internal_code)}
      ${field('Número de serie', h.serial_number)}
      ${ids.map(i => field(i.kind === 'QR' ? 'QR' : i.kind === 'IMEI' ? 'IMEI' : i.kind, i.value)).join('')}
      ${field('Proyecto', h.project)}
      ${field('Grupo', h.group)}
      ${field('Ubicación', h.location)}
      ${field('Custodia actual', h.custodian, h.custodian_person_id
        ? ` <a class="inline-link" data-goto="person" data-id="${esc(h.custodian_person_id)}">ver expediente</a>` : '')}
    </div>
    ${h.capabilities?.length ? `<p class="muted small">Capacidades del tipo: ${h.capabilities.map(c => `<code>${esc(c)}</code>`).join(' ')}</p>` : ''}
  </div>`;
}

const movementsTable = movements => table(
  ['Movimiento', 'Estado resultante', 'Ocurrió', 'Registrado', 'Responsable', 'Línea / estaca', 'Ubicación'],
  movements.map(m => `<tr>
    <td>${badge(m.movement_type)}</td><td>${esc(m.status_after || '—')}</td>
    <td>${fmt(m.occurred_at)}</td><td>${fmt(m.recorded_at)}</td>
    <td>${esc(m.responsible || '—')}</td>
    <td>${esc([m.line_code, m.stake_code].filter(Boolean).join(' / ') || '—')}</td>
    <td>${esc(m.location || '—')}</td></tr>`));

const custodyTable = custody => table(
  ['Responsable', 'Tipo', 'Proyecto', 'Desde', 'Hasta'],
  custody.map(c => `<tr class="${c.current ? 'row-current' : ''}">
    <td>${c.person_id ? `<button class="link" data-goto="person" data-id="${esc(c.person_id)}">${esc(c.person)}</button>` : '—'}</td>
    <td>${esc(c.assignment_type)}</td><td>${esc(c.project || '—')}</td>
    <td>${fmt(c.start_at)}</td><td>${c.current ? badge('vigente', 'ok') : fmt(c.end_at)}</td></tr>`));

const maintenanceSection = orders => orders.length ? orders.map(o => `
  <div class="engagement">
    <div class="engagement-head">
      <strong>Orden ${esc(o.id.slice(0, 8))}</strong>
      ${badge(o.status, o.status === 'CLOSED' ? 'ok' : 'warn')}
      <span class="muted small">${fmt(o.opened_at)} → ${o.closed_at ? fmt(o.closed_at) : 'abierta'}</span>
    </div>
    <div class="field-grid compact">
      ${field('Síntoma', o.symptom)}
      ${field('Código de falla', o.fault_code)}
      ${field('Diagnóstico', o.diagnosis)}
      ${field('Acción / reparación', o.action_taken)}
      ${field('Resultado', o.result)}
      ${field('Downtime', o.downtime_minutes != null ? `${o.downtime_minutes} min` : null)}
    </div>
    ${o.parts.length ? `<div class="subsection"><h4>Piezas</h4>
      ${table(['Componente', 'Serial retirado', 'Serial instalado', 'Cant.'], o.parts.map(p =>
        `<tr><td>${esc(p.component_type)}</td><td class="code">${esc(p.serial_removed || '—')}</td>
         <td class="code">${esc(p.serial_installed || '—')}</td><td>${esc(p.quantity)}</td></tr>`))}
    </div>` : ''}
  </div>`).join('') : emptyState('Sin intervenciones de taller registradas');

const healthSection = health => `
  <p class="muted small note">Una observación de salud/RUL es una <b>predicción</b>, no un hecho.
  Nunca da de baja un equipo automáticamente: la decisión es humana y queda registrada aparte.</p>
  ${table(['Observado', 'Fuente', 'SOH %', 'RUL (días)', 'Score', 'Confianza', 'Ciclos', 'Horas'],
    health.map(h => `<tr><td>${fmt(h.observed_at)}</td><td>${esc(h.source)}</td>
      <td>${esc(h.soh_percent ?? '—')}</td><td>${esc(h.rul_days ?? '—')}</td><td>${esc(h.health_score ?? '—')}</td>
      <td>${esc(h.confidence || '—')}</td><td>${esc(h.cycles ?? '—')}</td><td>${esc(h.operating_hours ?? '—')}</td></tr>`))}`;

const inventorySection = counts => `
  <p class="muted small note">Un faltante de inventario es una <b>observación</b>, no una pérdida definitiva.
  Control de Material concilia y decide.</p>
  ${table(['Inventario', 'Estado del inventario', 'Encontrado', 'Estado observado', 'Ubicación', 'Fecha'],
    counts.map(c => `<tr><td>${esc(c.session)}</td><td>${esc(c.session_status || '—')}</td>
      <td>${c.found ? badge('Sí', 'ok') : badge('No encontrado', 'bad')}</td>
      <td>${esc(c.observed_status_code || '—')}</td><td>${esc(c.location || '—')}</td><td>${fmt(c.counted_at)}</td></tr>`))}`;

const evidenceSection = records => table(
  ['Archivo', 'Origen', 'SHA-256', 'Tamaño', 'Registrada'],
  records.map(e => `<tr><td>${esc(e.name)}</td><td>${esc(e.source)}</td>
    <td class="code">${esc(String(e.sha256).slice(0, 16))}…</td>
    <td>${esc(e.size_bytes != null ? (e.size_bytes / 1024).toFixed(0) + ' KB' : '—')}</td>
    <td>${fmt(e.created_at)}</td></tr>`));

// --- Ficha de NODO -----------------------------------------------------------

async function node(params) {
  const d = await api('/api/dossier/asset/' + encodeURIComponent(params.id));
  const h = d.header;
  setTitle(h.label, 'NODO SÍSMICO · CICLO OPERACIONAL');

  /*
   * Bloque de estado actual. Deliberadamente muestra de DÓNDE sale el estado:
   * un nodo no se reduce a un campo "estado", se deriva de su historial y el
   * operador debe poder auditar esa derivación sin salir de la ficha.
   */
  const estado = d.current_state;
  const derived = estado.derived_from;
  const estadoBlock = `<div class="panel summary-card">
    <div class="panel-head"><h3>Situación actual</h3>${badge(estado.status_code, 'big')}</div>
    ${derived ? `<p class="muted small">Estado derivado del último movimiento registrado:</p>
    <div class="field-grid">
      ${field('Último movimiento', derived.movement_type)}
      ${field('Ocurrió', derived.occurred_at ? fmt(derived.occurred_at) : null)}
      ${field('Línea', derived.line_code)}
      ${field('Estaca', derived.stake_code)}
      ${field('Quien lo manejaba', derived.responsible)}
      ${field('Ubicación', estado.location)}
      ${field('Proyecto', estado.project)}
    </div>` : emptyState('Este nodo aún no registra movimientos; su estado es el de alta.')}
  </div>`;

  const opsTable = ops => table(
    ['Operación', 'Ocurrió', 'Registrado', 'Línea', 'Estaca', 'Resultado', 'Estado', 'Responsable', 'Participantes'],
    ops.map(o => `<tr class="${o.result_code && o.result_code !== 'OK' ? 'row-exception' : ''}">
      <td>${badge(o.operation_type)}</td><td>${fmt(o.occurred_at)}</td><td>${fmt(o.recorded_at)}</td>
      <td>${esc(o.line_code || '—')}</td>
      <td>${esc([o.stake_from, o.stake_to].filter(Boolean).join(' → ') || '—')}</td>
      <td>${o.result_code ? badge(o.result_code, o.result_code === 'OK' ? 'ok' : 'bad') : '—'}</td>
      <td>${esc(o.new_status_code || '—')}</td>
      <td>${esc(o.responsible || '—')}</td>
      <td>${esc((o.participants || []).join(', ') || '—')}</td></tr>`));

  $('#content').innerHTML = `
    ${dossierHeader({
      eyebrow: 'NODO · ' + (h.type_name || 'Nodo'),
      title: h.label,
      subtitle: `${h.technology || 'Tecnología no capturada'}${h.vendor ? ` · ${h.vendor}` : ''}`,
      chips: [
        { text: estado.status_code, tone: d.exceptions.length ? 'bad' : 'ok' },
        { text: estado.project || 'Sin proyecto' },
        { text: `${d.operations.length} operación(es)` }
      ],
      actions: `<button class="secondary" data-back>← Volver a Tracking Nodes</button>`
    })}
    ${estadoBlock}
    ${assetIdentityPanel(h)}
    ${d.exceptions.length ? `<div class="panel alert-panel">
      <h3>Excepciones registradas</h3>
      ${opsTable(d.exceptions)}
    </div>` : ''}
    <div class="panel">${tabs([
      { key: 'ops', label: 'Operaciones y lotes', count: d.operations.length,
        body: d.operations.length ? opsTable(d.operations) : emptyState('Sin operaciones registradas') },
      { key: 'mov', label: 'Movimientos', count: d.movements.length, body: movementsTable(d.movements) },
      { key: 'custodia', label: 'Custodia', count: d.custody.length, body: custodyTable(d.custody) },
      { key: 'taller', label: 'Taller / reparaciones', count: d.maintenance.length, body: maintenanceSection(d.maintenance) },
      { key: 'salud', label: 'Salud / RUL', count: d.health.length, body: healthSection(d.health) },
      { key: 'inv', label: 'Inventarios', count: d.inventory.length, body: inventorySection(d.inventory) },
      { key: 'ev', label: 'Evidencias', count: d.evidence.length, body: evidenceSection(d.evidence) },
      { key: 'tl', label: 'Historial completo', count: d.timeline.length, body: timeline(d.timeline) }
    ])}</div>`;
  bindTabs();
  bindLinks();
  $('[data-back]').onclick = () => navigate('nodes');
}

// --- Ficha de ACTIVO genérico ------------------------------------------------

async function asset(params) {
  const d = await api('/api/dossier/asset/' + encodeURIComponent(params.id));
  // El backend decide el dominio: si resulta ser un nodo o una unidad, se abre
  // la ficha correcta en vez de mostrarlo con una plantilla que no le queda.
  if (d.kind === 'node') return node(params);
  if (d.kind === 'transport-unit') return transportUnit(params);

  const h = d.header;
  setTitle(h.label, 'ACTIVO · ' + (h.type_name || 'MATERIAL').toUpperCase());
  $('#content').innerHTML = `
    ${dossierHeader({
      eyebrow: 'ACTIVO · ' + (h.type_name || 'Material'),
      title: h.label,
      subtitle: `${h.technology || 'Sin tecnología capturada'} · ${h.project || 'Sin proyecto'}`,
      chips: [
        { text: h.status_code },
        { text: h.custodian ? `Custodia: ${h.custodian}` : 'Sin custodia asignada', tone: h.custodian ? '' : 'warn' },
        { text: h.location || 'Sin ubicación' }
      ],
      actions: `<button class="secondary" data-back>← Volver a Activos</button>`
    })}
    ${assetIdentityPanel(h)}
    <div class="panel">${tabs([
      { key: 'custodia', label: 'Custodia y entregas', count: d.custody.length, body: custodyTable(d.custody) },
      { key: 'mov', label: 'Movimientos', count: d.movements.length, body: movementsTable(d.movements) },
      { key: 'inv', label: 'Inventarios', count: d.inventory.length, body: inventorySection(d.inventory) },
      { key: 'taller', label: 'Mantenimiento', count: d.maintenance.length, body: maintenanceSection(d.maintenance) },
      { key: 'salud', label: 'Salud / RUL', count: d.health.length, body: healthSection(d.health) },
      { key: 'ev', label: 'Evidencias', count: d.evidence.length, body: evidenceSection(d.evidence) },
      { key: 'tl', label: 'Historial completo', count: d.timeline.length, body: timeline(d.timeline) }
    ])}</div>`;
  bindTabs();
  bindLinks();
  $('[data-back]').onclick = () => navigate('assets');
}

// --- Ficha de UNIDAD DE TRANSPORTE -------------------------------------------

async function transportUnit(params) {
  const d = await api('/api/transport/units/' + encodeURIComponent(params.id));
  const h = d.header;
  const a = d.current_assignment;
  setTitle(h.label, 'UNIDAD DE TRANSPORTE');

  /*
   * Transporte se presenta por su asignación vigente, no por su ficha de
   * almacén: conductor, grupo, radio y teléfono son lo primero que necesita
   * ver quien despacha unidades.
   */
  const asignacion = `<div class="panel summary-card">
    <div class="panel-head"><h3>Asignación vigente</h3>
      ${badge(a?.availability || 'SIN ASIGNAR', a?.availability === 'AVAILABLE' ? 'ok' : a ? 'warn' : '')}</div>
    ${a ? `<div class="field-grid">
      ${field('Conductor', a.driver, a.driver_person_id
        ? ` <a class="inline-link" data-goto="person" data-id="${esc(a.driver_person_id)}">ver expediente</a>` : '')}
      ${field('Grupo', a.group)}
      ${field('Proyecto', a.project)}
      ${field('Ubicación', a.location)}
      ${field('Radio', a.radio)}
      ${field('Teléfono', a.phone)}
      ${field('Asignada desde', fmt(a.start_at))}
      ${field('Nota', a.note)}
    </div>` : emptyState('Esta unidad no tiene asignación vigente. Transporte puede asignarle conductor y grupo.')}
  </div>`;

  const abiertas = d.incidents.filter(i => i.status === 'OPEN');
  const canManage = can('transport.manage');

  const formAsignar = canManage ? `<div class="panel">
    <h3>Asignar / reasignar unidad</h3>
    <p class="muted small">La asignación anterior se cierra con fecha; no se sobrescribe.
      Quién conducía en una fecha pasada sigue siendo consultable.</p>
    <form id="assignForm" class="formgrid">
      <select name="driver_person_id"><option value="">Conductor…</option></select>
      <select name="group_id"><option value="">Grupo…</option></select>
      <select name="project_id"><option value="">Proyecto…</option></select>
      <select name="location_id"><option value="">Ubicación…</option></select>
      <select name="radio_asset_id"><option value="">Radio asociado…</option></select>
      <select name="phone_asset_id"><option value="">Teléfono asociado…</option></select>
      <select name="availability">
        <option value="ASSIGNED">Asignada</option>
        <option value="AVAILABLE">Disponible</option>
        <option value="WORKSHOP">En taller</option>
        <option value="DOWN">Fuera de servicio</option>
      </select>
      <input name="note" placeholder="Nota">
      <button class="wide">Guardar asignación</button>
      <div class="msg wide"></div>
    </form>
  </div>` : '';

  const formChecklist = canManage ? `<div class="panel">
    <h3>Registrar checklist</h3>
    <form id="checklistForm" class="formgrid">
      <select name="result">
        <option value="PASS">Sin hallazgos</option>
        <option value="PASS_WITH_FINDINGS">Con hallazgos menores</option>
        <option value="FAIL">Con falla</option>
      </select>
      <input name="odometer_km" type="number" min="0" placeholder="Odómetro (km)">
      <input name="fuel_level" placeholder="Nivel de combustible">
      <input class="wide" name="note" placeholder="Observaciones del checklist">
      <button class="wide">Registrar checklist</button>
      <div class="msg wide"></div>
    </form>
    <p class="muted small note">Un resultado con falla <b>no</b> inmoviliza la unidad automáticamente:
      queda registrado y Transporte decide la disponibilidad.</p>
  </div>` : '';

  const formIncidencia = can('cases.create') ? `<div class="panel">
    <h3>Reportar incidencia</h3>
    <p class="muted small">Cualquier área que presencie el hecho puede reportarlo.
      Sólo Transporte, autoridad del dominio, lo resuelve.</p>
    <form id="incidentForm" class="formgrid">
      <input name="incident_type" placeholder="Tipo (falla, ponchadura, choque…)" required>
      <select name="severity">
        <option value="LOW">Baja</option><option value="NORMAL" selected>Normal</option>
        <option value="HIGH">Alta</option><option value="CRITICAL">Crítica</option>
      </select>
      <textarea class="wide" name="summary" placeholder="Hechos observados" required></textarea>
      <button class="wide">Reportar</button>
      <div class="msg wide"></div>
    </form>
  </div>` : '';

  $('#content').innerHTML = `
    ${dossierHeader({
      eyebrow: 'TRANSPORTE · ' + (h.type_name || 'Unidad'),
      title: h.label,
      subtitle: a?.driver ? `Conductor: ${a.driver}` : 'Sin conductor asignado',
      chips: [
        { text: a?.availability || 'SIN ASIGNAR', tone: a?.availability === 'AVAILABLE' ? 'ok' : 'warn' },
        { text: abiertas.length ? `${abiertas.length} incidencia(s) abierta(s)` : 'Sin incidencias abiertas',
          tone: abiertas.length ? 'bad' : 'ok' },
        { text: h.project || 'Sin proyecto' }
      ],
      actions: `<button class="secondary" data-back>← Volver a Unidades</button>`
    })}
    ${asignacion}
    ${abiertas.length ? `<div class="panel alert-panel">
      <h3>Incidencias abiertas</h3>
      ${table(['Tipo', 'Severidad', 'Resumen', 'Conductor', 'Ocurrió', ''], abiertas.map(i => `<tr>
        <td>${badge(i.incident_type)}</td><td>${badge(i.severity, i.severity === 'CRITICAL' || i.severity === 'HIGH' ? 'bad' : 'warn')}</td>
        <td>${esc(i.summary)}</td><td>${esc(i.driver || '—')}</td><td>${fmt(i.occurred_at)}</td>
        <td>${canManage ? `<button class="link" data-resolve="${esc(i.id)}">Resolver</button>` : '—'}</td></tr>`))}
    </div>` : ''}
    ${formAsignar}${formChecklist}${formIncidencia}
    ${assetIdentityPanel(h)}
    <div class="panel">${tabs([
      { key: 'asig', label: 'Historial de asignaciones', count: d.assignments.length,
        body: table(['Conductor', 'Grupo', 'Proyecto', 'Radio', 'Teléfono', 'Disponibilidad', 'Desde', 'Hasta'],
          d.assignments.map(x => `<tr class="${x.current ? 'row-current' : ''}">
            <td>${esc(x.driver || '—')}</td><td>${esc(x.group || '—')}</td><td>${esc(x.project || '—')}</td>
            <td>${esc(x.radio || '—')}</td><td>${esc(x.phone || '—')}</td><td>${badge(x.availability)}</td>
            <td>${fmt(x.start_at)}</td><td>${x.current ? badge('vigente', 'ok') : fmt(x.end_at)}</td></tr>`)) },
      { key: 'chk', label: 'Checklist', count: d.checklists.length,
        body: table(['Resultado', 'Odómetro', 'Combustible', 'Conductor', 'Ocurrió', 'Registrado', 'Hallazgos'],
          d.checklists.map(c => `<tr>
            <td>${badge(c.result, c.result === 'PASS' ? 'ok' : c.result === 'FAIL' ? 'bad' : 'warn')}</td>
            <td>${esc(c.odometer_km ?? '—')}</td><td>${esc(c.fuel_level || '—')}</td>
            <td>${esc(c.driver || '—')}</td><td>${fmt(c.occurred_at)}</td><td>${fmt(c.recorded_at)}</td>
            <td>${esc((c.items || []).filter(i => !i.ok).map(i => i.label || i.code).join(', ') || '—')}</td></tr>`)) },
      { key: 'inc', label: 'Incidencias', count: d.incidents.length,
        body: table(['Tipo', 'Severidad', 'Estado', 'Resumen', 'Ocurrió', 'Resolución'], d.incidents.map(i => `<tr>
          <td>${badge(i.incident_type)}</td><td>${esc(i.severity)}</td>
          <td>${badge(i.status, i.status === 'OPEN' ? 'warn' : 'ok')}</td>
          <td>${esc(i.summary)}</td><td>${fmt(i.occurred_at)}</td><td>${esc(i.resolution || '—')}</td></tr>`)) },
      { key: 'taller', label: 'Mantenimiento', count: d.maintenance.length, body: maintenanceSection(d.maintenance) },
      { key: 'mov', label: 'Movimientos', count: d.movements.length, body: movementsTable(d.movements) },
      { key: 'ev', label: 'Evidencias', count: d.evidence.length, body: evidenceSection(d.evidence) },
      { key: 'tl', label: 'Historial completo', count: d.timeline.length, body: timeline(d.timeline) }
    ])}</div>`;

  bindTabs();
  bindLinks();
  $('[data-back]').onclick = () => navigate('transport');

  if (canManage) {
    // Los selectores se llenan con datos reales para no pedir UUIDs a mano.
    const [drivers, groups, projects, locations, assets, types] = await Promise.all([
      // personOptions() etiqueta con nombre + ID laboral: dos personas pueden
      // llamarse igual y el conductor debe quedar identificado sin ambigüedad.
      can('person.view') ? personOptions() : '',
      api('/api/groups'), api('/api/projects'), api('/api/locations'),
      can('assets.view') ? api('/api/assets') : [],
      can('assets.view') ? api('/api/asset-types') : []
    ]);
    // Qué activo puede ser radio o teléfono lo deciden las CAPACIDADES del tipo,
    // no su código: un tipo nuevo con capacidad `radio` aparece aquí solo.
    const conCapacidad = cap => new Set(types.filter(t => (t.capabilities || []).includes(cap)).map(t => t.code));
    const opt = (rows, value, label) => rows.map(r => `<option value="${esc(r[value])}">${esc(r[label])}</option>`).join('');
    const form = $('#assignForm');
    if (form) {
      form.driver_person_id.insertAdjacentHTML('beforeend', drivers);
      form.group_id.insertAdjacentHTML('beforeend', opt(groups, 'id', 'name'));
      form.project_id.insertAdjacentHTML('beforeend', opt(projects, 'id', 'name'));
      form.location_id.insertAdjacentHTML('beforeend', opt(locations, 'id', 'name'));
      const tiposRadio = conCapacidad('radio'), tiposTelefono = conCapacidad('phone');
      const radios = assets.filter(x => tiposRadio.has(x.type_code));
      const phones = assets.filter(x => tiposTelefono.has(x.type_code));
      form.radio_asset_id.insertAdjacentHTML('beforeend', opt(radios, 'id', 'label'));
      form.phone_asset_id.insertAdjacentHTML('beforeend', opt(phones, 'id', 'label'));
      if (a) form.availability.value = a.availability;
      form.onsubmit = async event => {
        event.preventDefault();
        const body = Object.fromEntries(new FormData(form));
        for (const key of Object.keys(body)) if (body[key] === '') body[key] = null;
        try {
          await api(`/api/transport/units/${encodeURIComponent(params.id)}/assignments`, { method: 'POST', body });
          msg(form, 'Asignación guardada', true);
          setTimeout(() => transportUnit(params), 400);
        } catch (error) { msg(form, error.message); }
      };
    }
    const checklistForm = $('#checklistForm');
    if (checklistForm) checklistForm.onsubmit = async event => {
      event.preventDefault();
      const body = Object.fromEntries(new FormData(checklistForm));
      body.odometer_km = body.odometer_km ? Number(body.odometer_km) : null;
      body.fuel_level = body.fuel_level || null;
      body.note = body.note || null;
      body.driver_person_id = a?.driver_person_id || null;
      try {
        await api(`/api/transport/units/${encodeURIComponent(params.id)}/checklists`, { method: 'POST', body });
        msg(checklistForm, 'Checklist registrado', true);
        setTimeout(() => transportUnit(params), 400);
      } catch (error) { msg(checklistForm, error.message); }
    };
    $$('[data-resolve]').forEach(btn => btn.onclick = async () => {
      const resolution = prompt('Resolución de Transporte para esta incidencia:');
      if (!resolution) return;
      try {
        await api(`/api/transport/incidents/${encodeURIComponent(btn.dataset.resolve)}/resolve`, { method: 'POST', body: { resolution } });
        transportUnit(params);
      } catch (error) { alert(error.message); }
    });
  }

  const incidentForm = $('#incidentForm');
  if (incidentForm) incidentForm.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(incidentForm));
    body.driver_person_id = a?.driver_person_id || null;
    try {
      await api(`/api/transport/units/${encodeURIComponent(params.id)}/incidents`, { method: 'POST', body });
      msg(incidentForm, 'Incidencia reportada', true);
      setTimeout(() => transportUnit(params), 400);
    } catch (error) { msg(incidentForm, error.message); }
  };
}

// --- Vistas de dominio · RRHH ------------------------------------------------

/** Opciones de persona reutilizables en los formularios que la requieren. */
async function personOptions() {
  const rows = await api('/api/persons');
  return rows.map(p => `<option value="${esc(p.id)}">${esc(p.full_name)} · ${esc(p.employment_id || 'sin ID')}</option>`).join('');
}

async function people() {
  setTitle('Personal', 'RECURSOS HUMANOS');
  const [projects] = await Promise.all([api('/api/projects')]);

  const alta = can('person.edit') ? `<div class="panel">
    <h3>Alta de persona</h3>
    <p class="muted small">El alta crea la <b>identidad</b> y su primera contratación.
      Una recontratación futura conservará el mismo expediente.</p>
    <form id="newPerson" class="formgrid">
      <input name="full_name" placeholder="Nombre completo" required>
      <input name="employment_id" placeholder="ID laboral" required>
      <input name="position" placeholder="Puesto / categoría">
      <select name="employer_type"><option value="DIRECT">Directo</option><option value="OUTSOURCING">Outsourcing</option></select>
      <input name="provider" placeholder="Empresa / proveedor">
      <input name="start_date" type="date" required>
      <select name="project_id"><option value="">Proyecto…</option>
        ${projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>
      <button class="wide">Registrar</button><div class="msg wide"></div>
    </form>
  </div>` : '';

  $('#content').innerHTML = `
    <div class="panel">
      <div class="toolbar">
        <input id="personSearch" placeholder="Buscar por nombre o ID laboral" aria-label="Buscar personal">
        <button id="personGo" class="secondary">Buscar</button>
      </div>
      <div id="personList"></div>
    </div>
    ${alta}`;

  async function load(q = '') {
    const rows = await api('/api/persons' + (q ? '?q=' + encodeURIComponent(q) : ''));
    $('#personList').innerHTML = table(['Nombre', 'ID laboral', 'Puesto', 'Grupo', 'Estado', ''], rows.map(p => `<tr>
      <td><button class="link" data-goto="person" data-id="${esc(p.id)}">${esc(p.full_name)}</button></td>
      <td class="code">${esc(p.employment_id || '—')}</td><td>${esc(p.position || '—')}</td>
      <td>${esc(p.group || '—')}</td>
      <td>${badge(p.active ? 'Activo' : 'Sin relación vigente', p.active ? 'ok' : 'warn')}</td>
      <td><button class="link" data-goto="person" data-id="${esc(p.id)}">abrir expediente</button></td></tr>`));
    bindLinks($('#personList'));
  }
  $('#personGo').onclick = () => load($('#personSearch').value);
  $('#personSearch').onkeydown = e => { if (e.key === 'Enter') load(e.target.value); };
  await load();

  const form = $('#newPerson');
  if (form) form.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form));
    body.project_id = body.project_id || null;
    body.provider = body.provider || null;
    body.position = body.position || null;
    try {
      const created = await api('/api/persons', { method: 'POST', body });
      navigate('person', { id: created.id });
    } catch (error) { msg(form, error.message); }
  };
}

async function attendance() {
  setTitle('Asistencia', 'RECURSOS HUMANOS');
  const [options, estados] = await Promise.all([personOptions(), api('/api/catalogs/ATTENDANCE_STATUS')]);
  $('#content').innerHTML = `<div class="panel">
    <h3>Captura manual de asistencia</h3>
    <p class="muted small">La captura manual y la importada conviven; el expediente indica el origen de cada día.</p>
    <form id="attForm" class="formgrid">
      <select name="person_id" required><option value="">Persona…</option>${options}</select>
      <input name="attendance_date" type="date" required>
      <select name="status" required>${estados.map(s => `<option value="${esc(s.code)}">${esc(s.name)}</option>`).join('')}</select>
      <button class="wide">Registrar</button><div class="msg wide"></div>
    </form>
  </div>`;
  $('#attForm').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    try {
      await api('/api/attendance', { method: 'POST', body: Object.fromEntries(new FormData(form)) });
      msg(form, 'Asistencia registrada', true);
    } catch (error) { msg(form, error.message); }
  };
}

async function epp() {
  setTitle('EPP', 'RECURSOS HUMANOS');
  const [options, rows] = await Promise.all([can('person.view') ? personOptions() : '', api('/api/epp/requests')]);
  $('#content').innerHTML = `
    ${can('epp.request') ? `<div class="panel">
      <h3>Solicitar cambio o reposición</h3>
      <p class="muted small">Solicitar no es entregar: RRHH es la autoridad que resuelve.</p>
      <form id="eppForm" class="formgrid">
        <select name="person_id" required><option value="">Persona…</option>${options}</select>
        <input name="item_type" placeholder="EPP: overol, guantes, botas…" required>
        <textarea class="wide" name="reason" placeholder="Motivo" required></textarea>
        <button class="wide">Registrar solicitud</button><div class="msg wide"></div>
      </form></div>` : ''}
    <div class="panel"><h3>Solicitudes</h3>
      ${table(['Persona', 'EPP', 'Motivo', 'Estado', 'Acción'], rows.map(r => `<tr>
        <td><button class="link" data-goto="person" data-id="${esc(r.person_id)}">ver persona</button></td>
        <td>${esc(r.item_type)}</td><td>${esc(r.reason)}</td>
        <td>${badge(r.status, r.status === 'APPROVED' ? 'ok' : r.status === 'PENDING' ? 'warn' : '')}</td>
        <td>${can('epp.validate_hr') && r.status === 'PENDING'
          ? `<button data-approve="${esc(r.id)}">Aprobar</button>
             <button class="secondary" data-reject="${esc(r.id)}">No procede</button>` : '—'}</td></tr>`))}
    </div>`;
  bindLinks();
  const form = $('#eppForm');
  if (form) form.onsubmit = async event => {
    event.preventDefault();
    try { await api('/api/epp/requests', { method: 'POST', body: Object.fromEntries(new FormData(form)) }); await epp(); }
    catch (error) { msg(form, error.message); }
  };
  const review = async (id, decision) => {
    const note = prompt(decision === 'APPROVED' ? 'Observación de aprobación:' : 'Motivo por el que no procede:', '') ?? '';
    await api(`/api/epp/requests/${encodeURIComponent(id)}/review`, { method: 'POST', body: { decision, note } });
    await epp();
  };
  $$('[data-approve]').forEach(b => b.onclick = () => review(b.dataset.approve, 'APPROVED'));
  $$('[data-reject]').forEach(b => b.onclick = () => review(b.dataset.reject, 'REJECTED'));
}

async function training() {
  setTitle('Capacitación', 'SEGURIDAD / HSE');
  const [options, courses, records] = await Promise.all([
    can('person.view') ? personOptions() : '', api('/api/training/courses'), api('/api/training/records')]);
  $('#content').innerHTML = `
    <p class="muted view-hint">RRHH programa y mantiene la lista de espera; Seguridad/HSE es quien acredita el curso.</p>
    ${can('training.schedule_hr') ? `<div class="panel">
      <h3>Catálogo y programación</h3>
      <form id="courseForm" class="formgrid">
        <input name="code" placeholder="Código del curso" required>
        <input name="name" placeholder="Nombre del curso" required>
        <button class="wide">Crear curso</button><div class="msg wide"></div>
      </form><hr>
      <form id="trainingForm" class="formgrid">
        <select name="person_id" required><option value="">Persona…</option>${options}</select>
        <select name="course_id" required><option value="">Curso…</option>
          ${courses.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select>
        <input name="scheduled_for" type="date">
        <input name="note" placeholder="Nota / lista de espera">
        <button class="wide">Programar</button><div class="msg wide"></div>
      </form></div>` : ''}
    <div class="panel"><h3>Seguimiento</h3>
      ${table(['Persona', 'Curso', 'Estado', 'Fecha', 'Acción'], records.map(r => `<tr>
        <td><button class="link" data-goto="person" data-id="${esc(r.person_id)}">ver persona</button></td>
        <td>${esc(courses.find(c => c.id === r.course_id)?.name || r.course_id)}</td>
        <td>${badge(r.state, r.state === 'COMPLETED' ? 'ok' : 'warn')}</td>
        <td>${r.scheduled_for ? fmtDate(r.scheduled_for) : '—'}</td>
        <td>${can('training.confirm_hse') && r.state !== 'COMPLETED'
          ? `<button data-complete="${esc(r.id)}">Acreditar</button>` : '—'}</td></tr>`))}
    </div>`;
  bindLinks();
  const courseForm = $('#courseForm');
  if (courseForm) courseForm.onsubmit = async event => {
    event.preventDefault();
    try { await api('/api/training/courses', { method: 'POST', body: Object.fromEntries(new FormData(courseForm)) }); await training(); }
    catch (error) { msg(courseForm, error.message); }
  };
  const trainingForm = $('#trainingForm');
  if (trainingForm) trainingForm.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(trainingForm));
    body.scheduled_for = body.scheduled_for || null;
    body.note = body.note || null;
    try { await api('/api/training/records', { method: 'POST', body }); await training(); }
    catch (error) { msg(trainingForm, error.message); }
  };
  $$('[data-complete]').forEach(b => b.onclick = async () => {
    await api(`/api/training/records/${encodeURIComponent(b.dataset.complete)}/complete`, { method: 'POST' });
    await training();
  });
}

async function cases() {
  setTitle('Incidencias y casos', 'SEGURIDAD / HSE');
  const [options, rows] = await Promise.all([can('person.view') ? personOptions() : '', api('/api/cases')]);
  $('#content').innerHTML = `
    <p class="muted view-hint">Un caso registra <b>hechos y evidencia</b>. El sistema no emite veredictos:
      la resolución la firma el área competente y queda auditada.</p>
    ${can('cases.create') ? `<div class="panel">
      <h3>Registrar hecho</h3>
      <form id="caseForm" class="formgrid">
        <select name="person_id"><option value="">Sin persona específica</option>${options}</select>
        <input name="case_type" placeholder="Tipo de caso" required>
        <textarea class="wide" name="summary" placeholder="Hechos observados (no veredicto)" required></textarea>
        <button class="wide">Registrar</button><div class="msg wide"></div>
      </form></div>` : ''}
    <div class="panel"><h3>Casos</h3>
      ${table(['Tipo', 'Persona', 'Resumen', 'Estado', 'Resolución'], rows.map(c => `<tr>
        <td>${esc(c.case_type)}</td>
        <td>${c.person_id ? `<button class="link" data-goto="person" data-id="${esc(c.person_id)}">ver</button>` : '—'}</td>
        <td>${esc(c.summary)}</td><td>${badge(c.status, c.status === 'OPEN' ? 'warn' : 'ok')}</td>
        <td>${can('cases.resolve') && c.status === 'OPEN'
          ? `<button data-resolve="${esc(c.id)}">Resolver</button>` : esc(c.resolution || '—')}</td></tr>`))}
    </div>`;
  bindLinks();
  const form = $('#caseForm');
  if (form) form.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form));
    body.person_id = body.person_id || null;
    try { await api('/api/cases', { method: 'POST', body }); await cases(); }
    catch (error) { msg(form, error.message); }
  };
  $$('[data-resolve]').forEach(b => b.onclick = async () => {
    const resolution = prompt('Resolución del área competente:');
    if (!resolution) return;
    await api(`/api/cases/${encodeURIComponent(b.dataset.resolve)}/resolve`, { method: 'POST', body: { resolution } });
    await cases();
  });
}

// --- Vistas de dominio · Transporte ------------------------------------------

async function transport() {
  setTitle('Unidades de transporte', 'TRANSPORTE');
  const units = await api('/api/transport/units');
  const disponibles = units.filter(u => u.availability === 'AVAILABLE').length;
  const conIncidencia = units.filter(u => u.open_incidents > 0).length;
  $('#content').innerHTML = `
    <div class="widget-grid compact-grid">
      <article class="widget size-SMALL"><h3>Unidades</h3>
        <div class="metric-value">${units.length}</div><div class="metric-hint">registradas</div></article>
      <article class="widget size-SMALL"><h3>Disponibles</h3>
        <div class="metric-value ok">${disponibles}</div><div class="metric-hint">listas para asignar</div></article>
      <article class="widget size-SMALL"><h3>Con incidencia</h3>
        <div class="metric-value ${conIncidencia ? 'bad' : 'ok'}">${conIncidencia}</div>
        <div class="metric-hint">incidencias abiertas</div></article>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Flota</h3>
        <span class="muted small">El vínculo unidad ↔ conductor ↔ grupo se declara aquí y se consulta desde otras áreas.</span></div>
      ${units.length ? table(
        ['Unidad', 'Disponibilidad', 'Conductor', 'Grupo', 'Proyecto', 'Radio', 'Teléfono', 'Últ. checklist', 'Incid.', ''],
        units.map(u => `<tr class="${u.open_incidents ? 'row-exception' : ''}">
          <td><button class="link" data-goto="transportUnit" data-id="${esc(u.id)}">${esc(u.label)}</button></td>
          <td>${badge(u.availability, u.availability === 'AVAILABLE' ? 'ok' : u.availability === 'DOWN' ? 'bad' : 'warn')}</td>
          <td>${u.driver_person_id
            ? `<button class="link" data-goto="person" data-id="${esc(u.driver_person_id)}">${esc(u.driver)}</button>`
            : '<span class="missing">Sin conductor</span>'}</td>
          <td>${esc(u.group || '—')}</td><td>${esc(u.project || '—')}</td>
          <td>${esc(u.radio || '—')}</td><td>${esc(u.phone || '—')}</td>
          <td>${u.last_checklist
            ? badge(u.last_checklist.result, u.last_checklist.result === 'PASS' ? 'ok' : 'warn')
            : '<span class="missing">sin checklist</span>'}</td>
          <td>${u.open_incidents ? badge(u.open_incidents, 'bad') : '0'}</td>
          <td><button class="link" data-goto="transportUnit" data-id="${esc(u.id)}">abrir ficha</button></td></tr>`))
        : `<div class="empty-state"><p>No hay unidades registradas.</p>
           <p class="muted small">Una unidad es un activo cuyo <b>tipo</b> declara la capacidad
           <code>transport</code>. Regístrela desde Control de Material › Activos, o cree el tipo
           en Administración › Catálogos.</p></div>`}
    </div>`;
  bindLinks();
}

async function checklists() {
  setTitle('Checklist de unidades', 'TRANSPORTE');
  const rows = await api('/api/transport/checklists');
  $('#content').innerHTML = `<div class="panel">
    <div class="panel-head"><h3>Checklist registrados</h3>
      <span class="muted small">Se conserva cuándo se revisó y cuándo se capturó.</span></div>
    ${table(['Unidad', 'Resultado', 'Odómetro', 'Combustible', 'Conductor', 'Ocurrió', 'Registrado', 'Hallazgos'],
      rows.map(c => `<tr class="${c.result === 'FAIL' ? 'row-exception' : ''}">
        <td><button class="link" data-goto="transportUnit" data-id="${esc(c.unit_asset_id)}">${esc(c.unit)}</button></td>
        <td>${badge(c.result, c.result === 'PASS' ? 'ok' : c.result === 'FAIL' ? 'bad' : 'warn')}</td>
        <td>${esc(c.odometer_km ?? '—')}</td><td>${esc(c.fuel_level || '—')}</td>
        <td>${esc(c.driver || '—')}</td><td>${fmt(c.occurred_at)}</td><td>${fmt(c.recorded_at)}</td>
        <td>${esc((c.findings || []).map(f => f.label || f.code).join(', ') || '—')}</td></tr>`))}
  </div>`;
  bindLinks();
}

async function transportIncidents() {
  setTitle('Incidencias de unidad', 'TRANSPORTE');
  const rows = await api('/api/transport/incidents');
  const abiertas = rows.filter(r => r.status === 'OPEN');
  $('#content').innerHTML = `
    ${abiertas.length ? `<div class="panel alert-panel">
      <h3>Abiertas · requieren resolución de Transporte</h3>
      ${table(['Unidad', 'Tipo', 'Severidad', 'Resumen', 'Conductor', 'Ocurrió', ''], abiertas.map(i => `<tr>
        <td><button class="link" data-goto="transportUnit" data-id="${esc(i.unit_asset_id)}">${esc(i.unit)}</button></td>
        <td>${badge(i.incident_type)}</td>
        <td>${badge(i.severity, ['HIGH', 'CRITICAL'].includes(i.severity) ? 'bad' : 'warn')}</td>
        <td>${esc(i.summary)}</td><td>${esc(i.driver || '—')}</td><td>${fmt(i.occurred_at)}</td>
        <td>${can('transport.manage') ? `<button class="link" data-resolve="${esc(i.id)}">Resolver</button>` : '—'}</td></tr>`))}
    </div>` : ''}
    <div class="panel"><h3>Historial de incidencias</h3>
      ${table(['Unidad', 'Tipo', 'Estado', 'Resumen', 'Ocurrió', 'Resolución'], rows.map(i => `<tr>
        <td><button class="link" data-goto="transportUnit" data-id="${esc(i.unit_asset_id)}">${esc(i.unit)}</button></td>
        <td>${esc(i.incident_type)}</td><td>${badge(i.status, i.status === 'OPEN' ? 'warn' : 'ok')}</td>
        <td>${esc(i.summary)}</td><td>${fmt(i.occurred_at)}</td><td>${esc(i.resolution || '—')}</td></tr>`))}
    </div>`;
  bindLinks();
  $$('[data-resolve]').forEach(b => b.onclick = async () => {
    const resolution = prompt('Resolución de Transporte:');
    if (!resolution) return;
    await api(`/api/transport/incidents/${encodeURIComponent(b.dataset.resolve)}/resolve`, { method: 'POST', body: { resolution } });
    await transportIncidents();
  });
}

// --- Vistas de dominio · Control de Material ---------------------------------

async function assets() {
  setTitle('Activos y material', 'CONTROL DE MATERIAL');
  const [types, statuses, projects] = await Promise.all([
    api('/api/asset-types'), api('/api/catalogs/ASSET_STATUS'), api('/api/projects')]);

  const alta = can('assets.create') ? `<div class="panel">
    <h3>Alta de activo</h3>
    <p class="muted small">La identidad del activo (serie, IMEI, QR, económico) sobrevive a los cambios de proyecto.</p>
    <form id="assetForm" class="formgrid">
      <select name="type_code" required><option value="">Tipo…</option>
        ${types.map(t => `<option value="${esc(t.code)}">${esc(t.name)}</option>`).join('')}</select>
      <input name="technology_code" placeholder="Tecnología (código)">
      <input name="internal_code" placeholder="Número interno / económico">
      <input name="serial_number" placeholder="Número de serie">
      <input name="imei" placeholder="IMEI"><input name="qr" placeholder="QR">
      <input name="economic" placeholder="Número económico adicional">
      <button class="wide">Registrar activo</button><div class="msg wide"></div>
    </form></div>` : '';

  $('#content').innerHTML = `
    <div class="panel">
      <div class="toolbar">
        <input id="assetSearch" placeholder="Serie, IMEI, QR o número económico" aria-label="Buscar activo">
        <select id="assetTypeFilter"><option value="">Todos los tipos</option>
          ${types.map(t => `<option value="${esc(t.code)}">${esc(t.name)}</option>`).join('')}</select>
        <select id="assetStatusFilter"><option value="">Todos los estados</option>
          ${statuses.map(s => `<option value="${esc(s.code)}">${esc(s.name)}</option>`).join('')}</select>
        <button id="assetGo" class="secondary">Buscar</button>
      </div>
      <div id="assetList"></div>
    </div>
    ${alta}`;

  async function load() {
    const params = new URLSearchParams();
    if ($('#assetSearch').value.trim()) params.set('q', $('#assetSearch').value.trim());
    if ($('#assetTypeFilter').value) params.set('type_code', $('#assetTypeFilter').value);
    if ($('#assetStatusFilter').value) params.set('status', $('#assetStatusFilter').value);
    const rows = await api('/api/assets' + (params.toString() ? '?' + params : ''));
    const critical = new Set(statuses.filter(s => s.metadata?.critical).map(s => s.code));
    $('#assetList').innerHTML = table(
      ['Activo', 'Tipo', 'Serie', 'Estado', 'Proyecto', 'Custodia', ''],
      rows.map(a => `<tr class="${critical.has(a.status_code) ? 'row-exception' : ''}">
        <td><button class="link" data-goto="asset" data-id="${esc(a.id)}">${esc(a.label)}</button></td>
        <td>${esc(a.type_name || '—')}</td><td class="code">${esc(a.serial_number || '—')}</td>
        <td>${badge(a.status_code, critical.has(a.status_code) ? 'bad' : '')}</td>
        <td>${esc(projects.find(p => p.id === a.project_id)?.name || '—')}</td>
        <td>${a.custodian_person_id
          ? `<button class="link" data-goto="person" data-id="${esc(a.custodian_person_id)}">ver responsable</button>`
          : '<span class="missing">Sin custodia</span>'}</td>
        <td><button class="link" data-goto="asset" data-id="${esc(a.id)}">abrir ficha</button></td></tr>`));
    bindLinks($('#assetList'));
  }
  $('#assetGo').onclick = load;
  $('#assetTypeFilter').onchange = load;
  $('#assetStatusFilter').onchange = load;
  $('#assetSearch').onkeydown = e => { if (e.key === 'Enter') load(); };
  await load();

  const form = $('#assetForm');
  if (form) form.onsubmit = async event => {
    event.preventDefault();
    const raw = Object.fromEntries(new FormData(form));
    const body = {
      type_code: raw.type_code,
      technology_code: raw.technology_code || null,
      internal_code: raw.internal_code || null,
      serial_number: raw.serial_number || null,
      identifiers: []
    };
    if (raw.imei) body.identifiers.push({ kind: 'IMEI', value: raw.imei, is_primary: true });
    if (raw.qr) body.identifiers.push({ kind: 'QR', value: raw.qr });
    if (raw.economic) body.identifiers.push({ kind: 'ECONOMIC_NUMBER', value: raw.economic });
    try {
      const created = await api('/api/assets', { method: 'POST', body });
      navigate('asset', { id: created.id });
    } catch (error) { msg(form, error.message); }
  };
}

async function nodes() {
  setTitle('Tracking Nodes', 'OPERACIÓN');
  const [types, statuses, operations, results, projects, groups, locations] = await Promise.all([
    api('/api/asset-types'), api('/api/catalogs/ASSET_STATUS'), api('/api/catalogs/NODE_OPERATION'),
    api('/api/catalogs/NODE_RESULT'), api('/api/projects'), api('/api/groups'), api('/api/locations')]);
  const nodeTypes = types.filter(t => (t.capabilities || []).includes('node_field'));
  const nodeAssets = nodeTypes.length
    ? (await Promise.all(nodeTypes.map(t => api('/api/assets?type_code=' + encodeURIComponent(t.code))))).flat()
    : [];
  const history = await api('/api/node-operations');
  const critical = new Set(statuses.filter(s => s.metadata?.critical).map(s => s.code));
  const porEstado = {};
  for (const n of nodeAssets) porEstado[n.status_code] = (porEstado[n.status_code] || 0) + 1;

  const registro = can('nodes.operate') ? `<div class="panel">
    <h3>Registrar operación de campo</h3>
    <p class="muted small">Cada operación genera historial. El estado del nodo se <b>deriva</b> de lo registrado;
      no se sobrescribe el pasado.</p>
    <form id="nodeOp" class="formgrid">
      <select name="operation_type" required>
        ${operations.map(o => `<option value="${esc(o.code)}">${esc(o.name)}</option>`).join('')}</select>
      <select name="asset_id" required><option value="">Nodo…</option>
        ${nodeAssets.map(n => `<option value="${esc(n.id)}">${esc(n.label)} · ${esc(n.status_code)}</option>`).join('')}</select>
      <select name="project_id"><option value="">Proyecto…</option>
        ${projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>
      <select name="group_id"><option value="">Grupo…</option>
        ${groups.map(g => `<option value="${esc(g.id)}">${esc(g.name)}</option>`).join('')}</select>
      <select name="location_id"><option value="">Ubicación…</option>
        ${locations.map(l => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join('')}</select>
      <input name="line_code" placeholder="Línea">
      <input name="stake_from" placeholder="Estaca origen"><input name="stake_to" placeholder="Estaca destino">
      <select name="result_code"><option value="">Resultado (opcional)…</option>
        ${results.map(r => `<option value="${esc(r.code)}">${esc(r.name)}</option>`).join('')}</select>
      <select name="responsible_person_id"><option value="">Responsable…</option></select>
      <input class="wide" name="note" placeholder="Nota de campo">
      <button class="wide">Registrar operación</button><div class="msg wide"></div>
    </form></div>` : '';

  $('#content').innerHTML = `
    <div class="widget-grid compact-grid">
      ${Object.entries(porEstado).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([code, count]) => `
        <article class="widget size-SMALL"><h3>${esc(statuses.find(s => s.code === code)?.name || code)}</h3>
          <div class="metric-value ${critical.has(code) ? 'bad' : ''}">${count}</div>
          <div class="metric-hint">nodos</div></article>`).join('') || emptyState('Sin nodos registrados')}
    </div>
    ${registro}
    <div class="panel">
      <div class="panel-head"><h3>Nodos</h3><span class="muted small">${nodeAssets.length} registrados</span></div>
      ${table(['Nodo', 'Tecnología', 'Estado', 'Proyecto', ''], nodeAssets.map(n => `<tr class="${critical.has(n.status_code) ? 'row-exception' : ''}">
        <td><button class="link" data-goto="node" data-id="${esc(n.id)}">${esc(n.label)}</button></td>
        <td>${esc(n.technology || '—')}</td>
        <td>${badge(n.status_code, critical.has(n.status_code) ? 'bad' : 'ok')}</td>
        <td>${esc(projects.find(p => p.id === n.project_id)?.name || '—')}</td>
        <td><button class="link" data-goto="node" data-id="${esc(n.id)}">ver ciclo operacional</button></td></tr>`))}
    </div>
    <div class="panel"><h3>Operaciones recientes</h3>
      ${table(['Operación', 'Ocurrió', 'Línea', 'Proyecto', 'Nodos'], history.slice(0, 40).map(o => `<tr>
        <td>${badge(o.operation_type)}</td><td>${fmt(o.occurred_at)}</td>
        <td>${esc(o.line_code || '—')}</td><td>${esc(projects.find(p => p.id === o.project_id)?.name || '—')}</td>
        <td>${esc(o.item_count ?? 0)}</td></tr>`))}
    </div>`;
  bindLinks();

  const form = $('#nodeOp');
  if (form) {
    if (can('person.view')) form.responsible_person_id.insertAdjacentHTML('beforeend', await personOptions());
    form.onsubmit = async event => {
      event.preventDefault();
      const raw = Object.fromEntries(new FormData(form));
      const body = {
        operation_type: raw.operation_type,
        project_id: raw.project_id || null, group_id: raw.group_id || null,
        location_id: raw.location_id || null, line_code: raw.line_code || null,
        participant_person_ids: raw.responsible_person_id ? [raw.responsible_person_id] : [],
        note: raw.note || null,
        items: [{
          asset_id: raw.asset_id, stake_from: raw.stake_from || null, stake_to: raw.stake_to || null,
          result_code: raw.result_code || null, responsible_person_id: raw.responsible_person_id || null
        }]
      };
      try { await api('/api/node-operations', { method: 'POST', body }); await nodes(); }
      catch (error) { msg(form, error.message); }
    };
  }
}

// --- Vistas de dominio · Taller / TX -----------------------------------------

async function maintenance() {
  setTitle('Órdenes de taller', 'TALLER / TX');
  const [orders, assetList, estados] = await Promise.all([
    api('/api/maintenance'),
    can('assets.view') ? api('/api/assets') : [],
    api('/api/catalogs/MAINTENANCE_STATUS')]);
  const abiertas = orders.filter(o => o.status !== 'CLOSED');

  /*
   * El taller se presenta por su flujo real —recepción, diagnóstico, prueba,
   * reparación, resultado— y no como un movimiento de custodia más. Una orden
   * abierta es trabajo pendiente y se muestra primero.
   */
  const recepcion = can('maintenance.manage') ? `<div class="panel">
    <h3>Recepción en taller</h3>
    <form id="maintForm" class="formgrid">
      <select name="asset_id" required><option value="">Activo recibido…</option>
        ${assetList.map(a => `<option value="${esc(a.id)}">${esc(a.label)} · ${esc(a.type_name || '')}</option>`).join('')}</select>
      <select name="priority"><option value="NORMAL">Prioridad normal</option>
        <option value="HIGH">Alta</option><option value="LOW">Baja</option></select>
      <input class="wide" name="symptom" placeholder="Síntoma reportado">
      <input name="fault_code" placeholder="Código de falla">
      <button class="wide">Abrir orden</button><div class="msg wide"></div>
    </form></div>` : '';

  $('#content').innerHTML = `
    <p class="muted view-hint">Un evento de taller describe la <b>intervención técnica</b> sobre el activo.
      No es un movimiento de custodia y se registra por separado.</p>
    ${recepcion}
    <div class="panel ${abiertas.length ? 'alert-panel' : ''}">
      <div class="panel-head"><h3>Órdenes abiertas</h3><span class="muted small">${abiertas.length}</span></div>
      ${abiertas.length ? abiertas.map(o => `
        <div class="engagement">
          <div class="engagement-head">
            <button class="link strong" data-goto="asset" data-id="${esc(o.asset_id)}">${esc(o.asset_label)}</button>
            ${badge(o.status, 'warn')}${badge(o.priority)}
            <span class="muted small">abierta ${fmt(o.opened_at)}</span>
          </div>
          <div class="field-grid compact">
            ${field('Síntoma', o.symptom)}${field('Código de falla', o.fault_code)}
            ${field('Diagnóstico', o.diagnosis)}${field('Acción', o.action_taken)}
          </div>
          ${can('maintenance.manage') ? `<div class="row-actions">
            <button class="secondary" data-update="${esc(o.id)}">Actualizar diagnóstico / cerrar</button>
            <button class="secondary" data-part="${esc(o.id)}">Registrar pieza</button>
          </div>` : ''}
        </div>`).join('') : emptyState('Sin órdenes abiertas en taller')}
    </div>
    <div class="panel"><h3>Historial de órdenes</h3>
      ${table(['Activo', 'Estado', 'Síntoma', 'Diagnóstico', 'Resultado', 'Downtime', 'Abierta', 'Cerrada'],
        orders.map(o => `<tr>
          <td><button class="link" data-goto="asset" data-id="${esc(o.asset_id)}">${esc(o.asset_label)}</button></td>
          <td>${badge(o.status, o.status === 'CLOSED' ? 'ok' : 'warn')}</td>
          <td>${esc(o.symptom || '—')}</td><td>${esc(o.diagnosis || '—')}</td><td>${esc(o.result || '—')}</td>
          <td>${esc(o.downtime_minutes != null ? o.downtime_minutes + ' min' : '—')}</td>
          <td>${fmt(o.opened_at)}</td><td>${fmt(o.closed_at)}</td></tr>`))}
    </div>`;
  bindLinks();

  const form = $('#maintForm');
  if (form) form.onsubmit = async event => {
    event.preventDefault();
    try { await api('/api/maintenance', { method: 'POST', body: Object.fromEntries(new FormData(form)) }); await maintenance(); }
    catch (error) { msg(form, error.message); }
  };
  $$('[data-update]').forEach(b => b.onclick = async () => {
    const estado = prompt(`Nuevo estado (${estados.map(s => s.code).join(', ')}):`, 'DIAGNOSIS');
    if (!estado) return;
    const diagnosis = prompt('Diagnóstico:', '') ?? '';
    const action = prompt('Acción / reparación realizada:', '') ?? '';
    const downtime = prompt('Downtime en minutos (opcional):', '') ?? '';
    try {
      await api(`/api/maintenance/${encodeURIComponent(b.dataset.update)}`, {
        method: 'PUT',
        body: {
          status: estado, diagnosis: diagnosis || null, action_taken: action || null,
          downtime_minutes: downtime ? Number(downtime) : null
        }
      });
      await maintenance();
    } catch (error) { alert(error.message); }
  });
  $$('[data-part]').forEach(b => b.onclick = async () => {
    const component = prompt('Componente:');
    if (!component) return;
    const removed = prompt('Serial retirado (opcional):', '') ?? '';
    const installed = prompt('Serial instalado (opcional):', '') ?? '';
    try {
      await api(`/api/maintenance/${encodeURIComponent(b.dataset.part)}/parts`, {
        method: 'POST',
        body: { component_type: component, serial_removed: removed || null, serial_installed: installed || null, quantity: 1 }
      });
      await maintenance();
    } catch (error) { alert(error.message); }
  });
}

// --- Vistas de dominio · Inventario, evidencias y cierre ---------------------

async function inventory(params = {}) {
  setTitle('Inventario físico', 'CONTROL DE MATERIAL');
  const [sessions, projects, locations] = await Promise.all([
    api('/api/inventory/sessions'), api('/api/projects'), api('/api/locations')]);
  const detail = params.id ? await api('/api/inventory/sessions/' + encodeURIComponent(params.id)) : null;

  $('#content').innerHTML = `
    <p class="muted view-hint">Un activo no encontrado durante un inventario es una <b>observación</b>.
      No se convierte en pérdida definitiva sin la conciliación de Control de Material.</p>
    ${can('inventory.manage') ? `<div class="panel">
      <h3>Abrir levantamiento</h3>
      <form id="invForm" class="formgrid">
        <input name="name" placeholder="Nombre / corte" required>
        <select name="project_id"><option value="">Proyecto…</option>
          ${projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>
        <select name="location_id"><option value="">Ubicación…</option>
          ${locations.map(l => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join('')}</select>
        <input name="notes" placeholder="Notas">
        <button class="wide">Abrir inventario</button><div class="msg wide"></div>
      </form></div>` : ''}
    <div class="panel"><h3>Levantamientos</h3>
      ${table(['Nombre', 'Estado', 'Proyecto', 'Ubicación', 'Inicio', ''], sessions.map(s => `<tr>
        <td>${esc(s.name)}</td><td>${badge(s.status, s.status === 'CLOSED' ? 'ok' : 'warn')}</td>
        <td>${esc(projects.find(p => p.id === s.project_id)?.name || '—')}</td>
        <td>${esc(locations.find(l => l.id === s.location_id)?.name || '—')}</td>
        <td>${fmt(s.started_at)}</td>
        <td><button class="link" data-inv="${esc(s.id)}">ver detalle</button>
          ${can('inventory.closeout') && s.status === 'OPEN'
            ? `<button class="link" data-close="${esc(s.id)}">conciliar y cerrar</button>` : ''}</td></tr>`))}
    </div>
    ${detail ? `<div class="panel">
      <div class="panel-head"><h3>${esc(detail.name)}</h3>${badge(detail.status)}</div>
      ${table(['Activo', 'Encontrado', 'Estado observado', 'Nota'], detail.counts.map(c => `<tr class="${c.found ? '' : 'row-exception'}">
        <td><button class="link" data-goto="asset" data-id="${esc(c.asset_id)}">${esc(c.label)}</button></td>
        <td>${c.found ? badge('Sí', 'ok') : badge('No encontrado', 'bad')}</td>
        <td>${esc(c.observed_status_code || '—')}</td><td>${esc(c.note || '—')}</td></tr>`))}
    </div>` : ''}`;
  bindLinks();

  const form = $('#invForm');
  if (form) form.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form));
    body.project_id = body.project_id || null;
    body.location_id = body.location_id || null;
    try { await api('/api/inventory/sessions', { method: 'POST', body }); await inventory(); }
    catch (error) { msg(form, error.message); }
  };
  $$('[data-inv]').forEach(b => b.onclick = () => navigate('inventory', { id: b.dataset.inv }));
  $$('[data-close]').forEach(b => b.onclick = async () => {
    if (!confirm('¿Cerrar y conciliar este inventario? Los faltantes quedan registrados como observación, no como baja.')) return;
    const result = await api(`/api/inventory/sessions/${encodeURIComponent(b.dataset.close)}/close`, { method: 'POST' });
    alert(`Inventario cerrado.\nEsperados: ${result.expected}\nContados: ${result.counted}\n` +
          `No encontrados: ${result.missing.length}\nInesperados: ${result.unexpected.length}`);
    await inventory();
  });
}

async function evidence() {
  setTitle('Evidencias', 'CONTROL DE MATERIAL');
  const [repositories, projects] = await Promise.all([api('/api/evidence/repositories'), api('/api/projects')]);
  const repoOptions = repositories.map(r => `<option value="${esc(r.id)}">${esc(r.name)} · ${esc(r.repository_type)}</option>`).join('');
  $('#content').innerHTML = `
    <p class="muted view-hint">Los archivos pesados pueden quedarse en el NAS. Server Oficina registra su relación con la
      entidad, la ruta, el hash SHA-256, el tamaño, el MIME, la procedencia y el usuario. Si un repositorio SMB deja de
      estar montado, la carga se <b>rechaza</b> en lugar de caer silenciosamente a disco local.</p>
    ${can('evidence.manage') ? `<div class="panel">
      <h3>Repositorio</h3>
      <form id="repoForm" class="formgrid">
        <input name="code" placeholder="Código" required><input name="name" placeholder="Nombre" required>
        <select name="repository_type"><option value="LOCAL">LOCAL</option><option value="SMB">SMB / NAS</option></select>
        <input class="wide" name="mount_point" placeholder="Punto de montaje" required>
        <input class="wide" name="canonical_uri" placeholder="URI canónica (opcional)">
        <button class="wide">Registrar repositorio</button><div class="msg wide"></div>
      </form></div>` : ''}
    <div class="panel"><h3>Repositorios configurados</h3>
      ${table(['Código', 'Nombre', 'Tipo', 'Punto de montaje', 'Activo'], repositories.map(r => `<tr>
        <td class="code">${esc(r.code)}</td><td>${esc(r.name)}</td><td>${badge(r.repository_type)}</td>
        <td class="code">${esc(r.mount_point)}</td><td>${r.active ? 'Sí' : 'No'}</td></tr>`))}
    </div>
    ${can('evidence.manage') ? `<div class="section-grid">
      <div class="panel"><h3>Cargar evidencia</h3>
        <form id="evUpload" class="formgrid">
          <select name="repository_id" required><option value="">Repositorio…</option>${repoOptions}</select>
          <select name="entity_type" required>
            <option value="PERSON">Persona</option><option value="ASSET">Activo</option>
            <option value="CASE">Caso</option><option value="PROJECT">Proyecto</option></select>
          <input name="entity_id" placeholder="ID de la entidad" required>
          <select name="project_id"><option value="">Proyecto…</option>
            ${projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>
          <input class="wide" name="file" type="file" required>
          <button class="wide">Subir</button><div class="msg wide"></div>
        </form></div>
      <div class="panel"><h3>Indexar archivo existente en NAS</h3>
        <p class="muted small">Registra un archivo que ya vive en el repositorio, sin moverlo ni copiarlo.</p>
        <form id="evExisting" class="formgrid">
          <select name="repository_id" required><option value="">Repositorio…</option>${repoOptions}</select>
          <select name="entity_type" required>
            <option value="PERSON">Persona</option><option value="ASSET">Activo</option>
            <option value="CASE">Caso</option><option value="PROJECT">Proyecto</option></select>
          <input name="entity_id" placeholder="ID de la entidad" required>
          <input class="wide" name="relative_path" placeholder="Ruta relativa dentro del repositorio" required>
          <select name="project_id"><option value="">Proyecto…</option>
            ${projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>
          <button class="wide">Indexar</button><div class="msg wide"></div>
        </form></div>
    </div>` : ''}`;

  const repoForm = $('#repoForm');
  if (repoForm) repoForm.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(repoForm));
    body.canonical_uri = body.canonical_uri || null;
    try { await api('/api/evidence/repositories', { method: 'POST', body }); await evidence(); }
    catch (error) { msg(repoForm, error.message); }
  };
  const upload = $('#evUpload');
  if (upload) upload.onsubmit = async event => {
    event.preventDefault();
    const data = new FormData(upload);
    if (!data.get('project_id')) data.delete('project_id');
    try {
      const result = await api('/api/evidence/upload', { method: 'POST', body: data });
      msg(upload, `Evidencia registrada · SHA ${String(result.sha256).slice(0, 12)}…`, true);
    } catch (error) { msg(upload, error.message); }
  };
  const existing = $('#evExisting');
  if (existing) existing.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(existing));
    body.project_id = body.project_id || null;
    try {
      const result = await api('/api/evidence/register-existing', { method: 'POST', body });
      msg(existing, result.already_registered ? 'Ya estaba registrada' : 'Archivo existente indexado', true);
    } catch (error) { msg(existing, error.message); }
  };
}

async function closeout() {
  setTitle('Cierre de material por proyecto', 'CONTROL DE MATERIAL');
  const projects = await api('/api/projects');
  $('#content').innerHTML = `
    <p class="muted view-hint">El cierre conserva un <b>corte auditable</b> del material del proyecto.
      No mueve activos ni los da de baja: las transferencias posteriores se registran como movimientos
      y no reescriben este corte.</p>
    <div class="panel"><h3>Proyectos</h3>
      ${table(['Código', 'Nombre', 'Estado', 'Inicio', 'Fin', ''], projects.map(p => `<tr>
        <td class="code">${esc(p.code)}</td><td>${esc(p.name)}</td>
        <td>${badge(p.status, p.status === 'CLOSED' ? 'ok' : '')}</td>
        <td>${p.start_date ? fmtDate(p.start_date) : '—'}</td><td>${p.end_date ? fmtDate(p.end_date) : '—'}</td>
        <td><button class="link" data-preview="${esc(p.id)}">vista previa del corte</button>
          ${p.status !== 'CLOSED' ? `<button class="link" data-closeout="${esc(p.id)}">cerrar proyecto</button>` : ''}</td></tr>`))}
    </div>
    <div id="closeoutPanel"></div>`;

  const render = snapshot => {
    $('#closeoutPanel').innerHTML = `<div class="panel">
      <div class="panel-head"><h3>Corte de material · ${esc(snapshot.project.code)}</h3>
        <span class="muted small">${snapshot.assets_total} activo(s)</span></div>
      <div class="widget-grid compact-grid">
        <article class="widget size-SMALL"><h3>Transferibles</h3>
          <div class="metric-value ok">${snapshot.transferable_assets.length}</div></article>
        <article class="widget size-SMALL"><h3>Excepciones críticas</h3>
          <div class="metric-value ${snapshot.critical_assets.length ? 'bad' : 'ok'}">${snapshot.critical_assets.length}</div></article>
      </div>
      <div class="section-grid">
        <div><h4>Por estado</h4><ul class="breakdown">
          ${Object.entries(snapshot.status_counts).map(([k, v]) => `<li><span>${esc(k)}</span><b>${v}</b></li>`).join('')}
        </ul></div>
        <div><h4>Material crítico</h4>
          ${snapshot.critical_assets.length
            ? `<ul class="breakdown">${snapshot.critical_assets.map(a =>
                `<li class="bad"><span>${esc(a.label)}</span><b>${esc(a.status_code)}</b></li>`).join('')}</ul>`
            : emptyState('Sin excepciones críticas')}</div>
      </div></div>`;
  };

  $$('[data-preview]').forEach(b => b.onclick = async () => {
    render(await api(`/api/projects/${encodeURIComponent(b.dataset.preview)}/material-closeout`));
  });
  $$('[data-closeout]').forEach(b => b.onclick = async () => {
    if (!confirm('¿Cerrar el proyecto y conservar un corte auditable del material?\n\n' +
                 'Esta acción NO mueve ni da de baja activos.')) return;
    const result = await api(`/api/projects/${encodeURIComponent(b.dataset.closeout)}/material-closeout`, {
      method: 'POST', body: { note: 'Cierre generado desde la interfaz' }
    });
    render(result.snapshot);
    setTimeout(() => closeout(), 900);
  });
}

// --- Vistas de administración ------------------------------------------------

async function imports() {
  setTitle('Importaciones', 'RECURSOS HUMANOS');
  $('#content').innerHTML = `
    <div class="panel">
      <h3>Asistencia y personal</h3>
      <p class="muted small">Primero se genera una vista previa. <b>Nada</b> se escribe en el expediente
        hasta confirmar, y el archivo original se conserva con su SHA-256.</p>
      <form id="imp" class="formgrid">
        <select name="kind"><option value="attendance">Asistencia</option><option value="personnel">Personal</option></select>
        <input name="file" type="file" accept=".xlsx,.xlsm,.csv" required>
        <button class="wide">Generar vista previa</button><div class="msg wide"></div>
      </form>
      <pre id="preview" class="muted"></pre>
      <button id="commit" class="hidden">Confirmar importación</button>
    </div>
    <div class="panel">
      <h3>Carga masiva de activos</h3>
      <p class="muted small">CSV con TYPE / TECHNOLOGY / INTERNAL_CODE / SERIAL / STATUS.
        Las columnas no reconocidas se conservan como metadatos en lugar de descartarse.</p>
      <form id="assetImp" class="formgrid">
        <input name="file" type="file" accept=".csv" required>
        <button class="wide">Vista previa de activos</button><div class="msg wide"></div>
      </form>
      <pre id="assetPreview" class="muted"></pre>
      <button id="assetCommit" class="hidden">Confirmar activos</button>
    </div>`;

  let batch = null;
  $('#imp').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    const data = new FormData();
    data.append('file', form.file.files[0]);
    try {
      const out = await api('/api/imports/' + form.kind.value + '/preview', { method: 'POST', body: data });
      batch = out.batch_id;
      $('#preview').textContent = JSON.stringify(out, null, 2);
      if (can('imports.commit')) $('#commit').classList.remove('hidden');
    } catch (error) { msg(form, error.message); }
  };
  $('#commit').onclick = async () => {
    const out = await api('/api/imports/' + batch + '/commit', { method: 'POST' });
    $('#preview').textContent += '\n\nCONFIRMADO\n' + JSON.stringify(out, null, 2);
    $('#commit').classList.add('hidden');
  };

  let assetBatch = null;
  $('#assetImp').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    const data = new FormData();
    data.append('file', form.file.files[0]);
    try {
      const out = await api('/api/assets/bulk/preview', { method: 'POST', body: data });
      assetBatch = out.batch_id;
      $('#assetPreview').textContent = JSON.stringify(out, null, 2);
      if (out.can_commit) $('#assetCommit').classList.remove('hidden');
    } catch (error) { msg(form, error.message); }
  };
  $('#assetCommit').onclick = async () => {
    const out = await api('/api/assets/bulk/' + assetBatch + '/commit', { method: 'POST' });
    $('#assetPreview').textContent += '\n\nCONFIRMADO\n' + JSON.stringify(out, null, 2);
    $('#assetCommit').classList.add('hidden');
  };
}

async function projects() {
  setTitle('Proyectos y ubicaciones', 'ADMINISTRACIÓN');
  const [projectRows, locationRows, tipos] = await Promise.all([
    api('/api/projects'), api('/api/locations'), api('/api/catalogs/LOCATION_TYPE')]);
  $('#content').innerHTML = `
    <p class="muted view-hint">Las ubicaciones y campamentos son <b>datos configurables</b>.
      Ningún campamento está escrito en el código.</p>
    <div class="section-grid">
      <div class="panel"><h3>Proyectos</h3>
        ${can('projects.manage') ? `<form id="projForm" class="formgrid">
          <input name="code" placeholder="Código" required><input name="name" placeholder="Nombre" required>
          <input name="start_date" type="date"><button class="wide">Crear proyecto</button><div class="msg wide"></div>
        </form><hr>` : ''}
        ${table(['Código', 'Nombre', 'Estado'], projectRows.map(p =>
          `<tr><td class="code">${esc(p.code)}</td><td>${esc(p.name)}</td><td>${badge(p.status)}</td></tr>`))}
      </div>
      <div class="panel"><h3>Ubicaciones</h3>
        ${can('locations.manage') ? `<form id="locForm" class="formgrid">
          <input name="code" placeholder="Código" required><input name="name" placeholder="Nombre" required>
          <select name="location_type">${tipos.map(t => `<option value="${esc(t.code)}">${esc(t.name)}</option>`).join('')}</select>
          <select name="project_id"><option value="">Sin proyecto</option>
            ${projectRows.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>
          <button class="wide">Crear ubicación</button><div class="msg wide"></div>
        </form><hr>` : ''}
        ${table(['Código', 'Nombre', 'Tipo'], locationRows.map(l =>
          `<tr><td class="code">${esc(l.code)}</td><td>${esc(l.name)}</td><td>${badge(l.location_type)}</td></tr>`))}
      </div>
    </div>`;
  const projForm = $('#projForm');
  if (projForm) projForm.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(projForm));
    body.start_date = body.start_date || null;
    try { await api('/api/projects', { method: 'POST', body }); await projects(); }
    catch (error) { msg(projForm, error.message); }
  };
  const locForm = $('#locForm');
  if (locForm) locForm.onsubmit = async event => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(locForm));
    body.project_id = body.project_id || null;
    try { await api('/api/locations', { method: 'POST', body }); await projects(); }
    catch (error) { msg(locForm, error.message); }
  };
}

async function roles() {
  setTitle('Perfiles y permisos', 'ADMINISTRACIÓN');
  const [permissions, roleRows, areas] = await Promise.all([
    api('/api/permissions'), api('/api/roles'), api('/api/areas')]);
  const roleAreas = await Promise.all(roleRows.map(r => api('/api/roles/' + encodeURIComponent(r.name) + '/area')));
  const areaOf = Object.fromEntries(roleAreas.map(x => [x.role, x]));

  $('#content').innerHTML = `
    <p class="muted view-hint">El <b>área</b> agrupa la navegación y la vista resumen del departamento.
      Los <b>permisos</b> son lo único que autoriza una operación.</p>
    <div class="section-grid">
      <div class="panel">
        <h3>Crear perfil</h3>
        <form id="roleForm">
          <div class="formgrid">
            <input name="name" placeholder="Nombre del perfil" required>
            <input name="description" placeholder="Descripción">
          </div>
          <h4>Permisos</h4>
          <div class="checkbox-grid scrollbox">
            ${permissions.map(p => `<label class="check">
              <input type="checkbox" name="perm" value="${esc(p.code)}">
              <span><b>${esc(p.code)}</b><br><small class="muted">${esc(p.description)}</small></span></label>`).join('')}
          </div>
          <button style="margin-top:10px">Crear perfil</button><div class="msg"></div>
        </form>
      </div>
      <div class="panel"><h3>Perfiles existentes</h3>
        ${roleRows.map(r => `<div class="mini-card">
          <strong>${esc(r.name)}</strong>
          <div class="muted small">${esc(r.description || '')}</div>
          <div class="small">${r.permissions.length} permiso(s)</div>
          <label class="inline-field">Área
            <select data-role-area="${esc(r.name)}">
              ${areas.map(a => `<option value="${esc(a.code)}" ${areaOf[r.name]?.area_code === a.code ? 'selected' : ''}>
                ${esc(a.name)}</option>`).join('')}
            </select>
          </label>
        </div>`).join('')}
      </div>
    </div>`;

  $('#roleForm').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    const body = {
      name: form.name.value, description: form.description.value,
      permissions: $$('#roleForm input[name="perm"]:checked').map(x => x.value)
    };
    try { await api('/api/roles', { method: 'POST', body }); await roles(); }
    catch (error) { msg(form, error.message); }
  };
  $$('[data-role-area]').forEach(select => select.onchange = async () => {
    try {
      await api('/api/roles/' + encodeURIComponent(select.dataset.roleArea) + '/area',
        { method: 'PUT', body: { area_code: select.value } });
    } catch (error) { alert(error.message); }
  });
}

async function authority() {
  setTitle('Autoridad sobre el dato', 'ADMINISTRACIÓN');
  const data = await api('/api/areas/authority');
  const areaName = code => data.areas[code]?.name || code;
  $('#content').innerHTML = `
    <p class="muted view-hint">Server Oficina es compartido, pero cada dato tiene un área que responde por él.
      Compartir el Tracking Core no significa que cualquiera pueda modificar cualquier cosa.</p>
    <div class="panel">
      <div class="panel-head"><h3>Matriz de gobierno del dato</h3>
        <span class="muted small">Tus áreas: ${data.my_areas.map(a => areaName(a)).join(', ') || '—'}</span></div>
      ${table(['Dominio de información', 'Autoridad', 'Puede consultar', 'Puede proponer', 'Puede confirmar'],
        data.domains.map(d => {
          const mine = data.my_areas.includes(d.authority);
          return `<tr class="${mine ? 'row-current' : ''}">
            <td><strong>${esc(d.name)}</strong>${d.note ? `<div class="muted small">${esc(d.note)}</div>` : ''}</td>
            <td>${badge(areaName(d.authority), mine ? 'ok' : '')}</td>
            <td class="small">${esc(d.consult.map(areaName).join(', ') || '—')}</td>
            <td class="small">${esc(d.propose.map(areaName).join(', ') || '—')}</td>
            <td class="small">${esc(d.confirm.map(areaName).join(', ') || '—')}</td></tr>`;
        }))}
    </div>`;
}

async function catalogs() {
  setTitle('Catálogos', 'ADMINISTRACIÓN');
  const [names, types] = await Promise.all([api('/api/catalogs'), api('/api/asset-types')]);
  $('#content').innerHTML = `
    <p class="muted view-hint">Estados, movimientos, resultados, tipos y tecnologías viven en la base de datos.
      Agregar un código nuevo no requiere cambiar el programa.</p>
    <div class="panel">
      <div class="toolbar">
        <select id="catName">${names.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join('')}</select>
        <button id="catLoad" class="secondary">Cargar catálogo</button>
      </div>
      <div id="catItems"></div>
    </div>
    <div class="section-grid">
      <div class="panel"><h3>Tipos de activo</h3>
        <p class="muted small">Las <b>capacidades</b> deciden el comportamiento: <code>node_field</code> abre la ficha de
          nodo, <code>transport</code> la de unidad. Nunca se decide por el nombre del tipo.</p>
        <form id="typeForm" class="formgrid">
          <input name="code" placeholder="Código" required><input name="name" placeholder="Nombre" required>
          <input class="wide" name="capabilities" placeholder="Capacidades separadas por coma: custody,maintenance,node_field">
          <button class="wide">Crear tipo</button><div class="msg wide"></div>
        </form><hr>
        ${table(['Código', 'Nombre', 'Capacidades'], types.map(t =>
          `<tr><td class="code">${esc(t.code)}</td><td>${esc(t.name)}</td>
           <td class="small">${(t.capabilities || []).map(c => `<code>${esc(c)}</code>`).join(' ') || '—'}</td></tr>`))}
      </div>
      <div class="panel"><h3>Tecnologías</h3>
        <form id="techForm" class="formgrid">
          <input name="code" placeholder="Código" required><input name="name" placeholder="Nombre" required>
          <input name="vendor" placeholder="Fabricante"><button class="wide">Crear tecnología</button>
          <div class="msg wide"></div>
        </form>
      </div>
    </div>`;

  async function loadCatalog() {
    const name = $('#catName').value;
    const rows = await api('/api/catalogs/' + encodeURIComponent(name) + '?include_inactive=true');
    $('#catItems').innerHTML = `
      ${table(['Código', 'Nombre', 'Activo', 'Metadatos'], rows.map(x =>
        `<tr><td class="code">${esc(x.code)}</td><td>${esc(x.name)}</td><td>${x.active ? 'Sí' : 'No'}</td>
         <td class="code small">${esc(JSON.stringify(x.metadata))}</td></tr>`))}
      <hr>
      <form id="catForm" class="formgrid">
        <input name="code" placeholder="Nuevo código" required><input name="name" placeholder="Nombre" required>
        <textarea class="wide" name="metadata" placeholder='Metadatos JSON opcionales, ej. {"critical":true}'></textarea>
        <button class="wide">Agregar al catálogo</button><div class="msg wide"></div>
      </form>`;
    $('#catForm').onsubmit = async event => {
      event.preventDefault();
      const form = event.target;
      let metadata = {};
      try { metadata = form.metadata.value ? JSON.parse(form.metadata.value) : {}; }
      catch { return msg(form, 'El JSON de metadatos no es válido'); }
      try {
        await api('/api/catalogs/' + encodeURIComponent(name),
          { method: 'POST', body: { code: form.code.value, name: form.name.value, metadata } });
        await loadCatalog();
      } catch (error) { msg(form, error.message); }
    };
  }
  $('#catLoad').onclick = loadCatalog;
  await loadCatalog();

  $('#typeForm').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    const body = {
      code: form.code.value, name: form.name.value,
      capabilities: form.capabilities.value.split(',').map(x => x.trim()).filter(Boolean), metadata: {}
    };
    try { await api('/api/asset-types', { method: 'POST', body }); await catalogs(); }
    catch (error) { msg(form, error.message); }
  };
  $('#techForm').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    try {
      await api('/api/asset-technologies', {
        method: 'POST',
        body: { code: form.code.value, name: form.name.value, vendor: form.vendor.value || null, metadata: {} }
      });
      await catalogs();
    } catch (error) { msg(form, error.message); }
  };
}

async function users() {
  setTitle('Usuarios', 'ADMINISTRACIÓN');
  const [rows, roleRows] = await Promise.all([api('/api/users'), api('/api/roles')]);
  $('#content').innerHTML = `
    <div class="panel"><h3>Crear usuario</h3>
      <form id="userForm" class="formgrid">
        <input name="display_name" placeholder="Nombre" required>
        <input name="username" placeholder="Usuario" required>
        <input name="password" type="password" minlength="10" placeholder="Contraseña (mín. 10)" required>
        <select name="roles" required>${roleRows.map(r => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('')}</select>
        <button class="wide">Crear usuario</button><div class="msg wide"></div>
      </form></div>
    <div class="panel"><h3>Usuarios</h3>
      ${table(['Usuario', 'Nombre', 'Perfiles', 'Activo'], rows.map(u => `<tr>
        <td class="code">${esc(u.username)}</td><td>${esc(u.display_name)}</td>
        <td>${esc(u.roles.join(', '))}</td><td>${u.active ? 'Sí' : 'No'}</td></tr>`))}
    </div>`;
  $('#userForm').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    const body = Object.fromEntries(new FormData(form));
    body.roles = [body.roles];
    try { await api('/api/users', { method: 'POST', body }); await users(); }
    catch (error) { msg(form, error.message); }
  };
}

async function audit() {
  setTitle('Auditoría', 'ADMINISTRACIÓN');
  const rows = await api('/api/audit');
  $('#content').innerHTML = `<div class="panel"><h3>Registro auditable</h3>
    ${table(['Fecha', 'Acción', 'Entidad', 'ID', 'Usuario'], rows.map(x => `<tr>
      <td>${fmt(x.created_at)}</td><td>${badge(x.action)}</td><td>${esc(x.entity_type)}</td>
      <td class="code small">${esc(x.entity_id || '—')}</td><td class="code small">${esc(x.user_id || '—')}</td></tr>`))}
  </div>`;
}

// --- Modo DEV · configuración del Dashboard ---------------------------------
/*
 * Pantalla de administración que pide el apartado 9 del encargo: MOSTRAR,
 * OCULTAR, ORDENAR, CONFIGURAR y ASIGNAR A PERFIL/ÁREA.
 *
 * Trabaja sobre una copia en memoria de la composición y sólo persiste al pulsar
 * "Guardar". Así el administrador puede reordenar varias tarjetas y arrepentirse
 * sin dejar el dashboard a medias para el resto de la oficina.
 */

let DEV_STATE = null;

async function devDashboard(params = {}) {
  setTitle('Modo DEV · Vista resumen', 'ADMINISTRACIÓN');
  const [dashboards, catalog] = await Promise.all([api('/api/dashboards'), api('/api/dev/widgets')]);
  const key = params.key || DEV_STATE?.key || dashboards[0]?.key;
  if (!key) { $('#content').innerHTML = emptyState('No hay vistas resumen definidas.'); return; }
  const layout = await api('/api/dev/dashboards/' + encodeURIComponent(key));
  const roleRows = await api('/api/roles');

  DEV_STATE = { key, placements: layout.placements.map(p => ({ ...p })) };
  renderDev(dashboards, catalog, roleRows, layout.dashboard);
}

function renderDev(dashboards, catalog, roleRows, info) {
  const placed = new Set(DEV_STATE.placements.map(p => p.widget_key));
  const available = catalog.widgets.filter(w => !placed.has(w.key));

  $('#content').innerHTML = `
    <div class="dashboard-switch">
      ${dashboards.map(d => `<button class="chip ${d.key === DEV_STATE.key ? 'active' : ''}"
        data-dash="${esc(d.key)}">${esc(d.name)}</button>`).join('')}
    </div>
    <p class="muted view-hint">Configura <strong>${esc(info.name)}</strong>.
      Los cambios se aplican al pulsar «Guardar composición».
      Un widget sólo se muestra a quien además tenga su permiso: la restricción por perfil
      <b>acota</b>, nunca amplía.</p>

    <div class="panel">
      <div class="panel-head"><h3>Widgets colocados</h3>
        <span class="muted small">${DEV_STATE.placements.length} colocado(s)</span></div>
      ${DEV_STATE.placements.length ? `<div class="dev-list">
        ${DEV_STATE.placements.map((p, index) => `
          <div class="dev-row ${p.orphan ? 'orphan' : ''} ${p.visible ? '' : 'hidden-widget'}">
            <div class="dev-order">
              <button class="icon" data-up="${index}" ${index === 0 ? 'disabled' : ''} title="Subir">▲</button>
              <button class="icon" data-down="${index}" ${index === DEV_STATE.placements.length - 1 ? 'disabled' : ''} title="Bajar">▼</button>
            </div>
            <div class="dev-main">
              <strong>${esc(p.title)}</strong>
              ${p.orphan ? badge('widget retirado en esta versión', 'bad')
                         : `${badge(catalog.areas[p.area] || p.area)}${badge(p.kind)}`}
              <div class="muted small code">${esc(p.widget_key)}${p.permission ? ` · requiere ${esc(p.permission)}` : ''}</div>
            </div>
            <div class="dev-controls">
              <label class="inline-field">Título
                <input data-title="${index}" value="${esc(p.title_override || '')}" placeholder="(por defecto)"></label>
              <label class="inline-field">Tamaño
                <select data-size="${index}">
                  ${catalog.sizes.map(s => `<option value="${esc(s)}" ${p.size === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}
                </select></label>
              <label class="inline-field">Sólo perfiles
                <select data-roles="${index}" multiple size="3">
                  ${roleRows.map(r => `<option value="${esc(r.name)}"
                    ${(p.role_names || []).includes(r.name) ? 'selected' : ''}>${esc(r.name)}</option>`).join('')}
                </select></label>
              <label class="inline-check">
                <input type="checkbox" data-visible="${index}" ${p.visible ? 'checked' : ''}> Mostrar</label>
              <button class="secondary small-btn" data-remove="${index}">Quitar</button>
            </div>
          </div>`).join('')}
      </div>` : emptyState('Esta vista resumen no tiene widgets colocados.')}
      <div class="row-actions">
        <button id="devSave">Guardar composición</button>
        <button id="devReload" class="secondary">Descartar cambios</button>
      </div>
      <div class="msg" id="devMsg"></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h3>Vistas resumen</h3>
        <span class="muted small">Las del sistema se desactivan, no se eliminan.</span></div>
      <form id="devNewDash" class="formgrid">
        <input name="key" placeholder="Clave (ej. almacen-central)" required>
        <input name="name" placeholder="Nombre visible" required>
        <select name="area_code">
          ${Object.entries(catalog.areas).map(([code, nombre]) =>
            `<option value="${esc(code)}">${esc(nombre)}</option>`).join('')}
        </select>
        <input name="description" placeholder="Descripción">
        <button class="wide">Crear vista resumen</button>
        <div class="msg wide"></div>
      </form>
      <div class="row-actions">
        ${info.is_system
          ? `<button class="secondary" id="devToggleActive">${info.active === false ? 'Reactivar' : 'Desactivar'} «${esc(info.name)}»</button>`
          : `<button class="secondary" id="devDeleteDash">Eliminar «${esc(info.name)}»</button>`}
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h3>Catálogo de widgets disponibles</h3>
        <span class="muted small">${available.length} sin colocar</span></div>
      <p class="muted small">Este catálogo se genera desde el registro en código
        (<code>app/services/widgets.py</code>). Para crear uno nuevo consulte
        <code>docs/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md</code>.</p>
      ${available.length ? `<div class="dev-catalog">
        ${available.map(w => `<div class="mini-card">
          <strong>${esc(w.title)}</strong>
          <div>${badge(catalog.areas[w.area] || w.area)}${badge(w.kind)}</div>
          <div class="muted small">${esc(w.description)}</div>
          <div class="muted small code">requiere ${esc(w.permission)}</div>
          <button class="secondary small-btn" data-add="${esc(w.key)}">Agregar</button>
        </div>`).join('')}
      </div>` : emptyState('Todos los widgets del catálogo ya están colocados en esta vista.')}
    </div>`;

  const rerender = () => renderDev(dashboards, catalog, roleRows, info);

  $$('[data-dash]').forEach(b => b.onclick = () => { DEV_STATE = null; navigate('devDashboard', { key: b.dataset.dash }); });

  $('#devNewDash').onsubmit = async event => {
    event.preventDefault();
    const form = event.target;
    const body = Object.fromEntries(new FormData(form));
    try {
      await api('/api/dev/dashboards', { method: 'POST', body });
      DEV_STATE = null;
      navigate('devDashboard', { key: body.key.trim().toLowerCase() });
    } catch (error) { msg(form, error.message); }
  };
  const toggleActive = $('#devToggleActive');
  if (toggleActive) toggleActive.onclick = async () => {
    // Desactivar es reversible y conserva la composición; por eso las vistas
    // del sistema se desactivan en lugar de borrarse.
    await api('/api/dev/dashboards/' + encodeURIComponent(info.key),
      { method: 'PATCH', body: { active: info.active === false } });
    DEV_STATE = null;
    navigate('devDashboard', { key: info.key });
  };
  const deleteDash = $('#devDeleteDash');
  if (deleteDash) deleteDash.onclick = async () => {
    if (!confirm(`¿Eliminar la vista resumen «${info.name}»?\n\n` +
                 'Se perderá su composición. Los widgets del catálogo no se ven afectados.')) return;
    try {
      await api('/api/dev/dashboards/' + encodeURIComponent(info.key), { method: 'DELETE' });
      DEV_STATE = null;
      navigate('devDashboard');
    } catch (error) { alert(error.message); }
  };
  $$('[data-up]').forEach(b => b.onclick = () => {
    const i = Number(b.dataset.up);
    [DEV_STATE.placements[i - 1], DEV_STATE.placements[i]] = [DEV_STATE.placements[i], DEV_STATE.placements[i - 1]];
    rerender();
  });
  $$('[data-down]').forEach(b => b.onclick = () => {
    const i = Number(b.dataset.down);
    [DEV_STATE.placements[i + 1], DEV_STATE.placements[i]] = [DEV_STATE.placements[i], DEV_STATE.placements[i + 1]];
    rerender();
  });
  $$('[data-remove]').forEach(b => b.onclick = () => {
    DEV_STATE.placements.splice(Number(b.dataset.remove), 1);
    rerender();
  });
  $$('[data-add]').forEach(b => b.onclick = () => {
    const w = catalog.widgets.find(x => x.key === b.dataset.add);
    DEV_STATE.placements.push({
      widget_key: w.key, title: w.title, area: w.area, kind: w.kind, permission: w.permission,
      visible: true, size: w.default_size, title_override: null, role_names: [], options: {}, orphan: false
    });
    rerender();
  });
  // Los cambios de campo se aplican al estado en memoria sin redibujar, para no
  // perder el foco mientras se escribe un título.
  $$('[data-title]').forEach(input => input.oninput = () => {
    DEV_STATE.placements[Number(input.dataset.title)].title_override = input.value.trim() || null;
  });
  $$('[data-size]').forEach(select => select.onchange = () => {
    DEV_STATE.placements[Number(select.dataset.size)].size = select.value;
  });
  $$('[data-roles]').forEach(select => select.onchange = () => {
    DEV_STATE.placements[Number(select.dataset.roles)].role_names = [...select.selectedOptions].map(o => o.value);
  });
  $$('[data-visible]').forEach(input => input.onchange = () => {
    DEV_STATE.placements[Number(input.dataset.visible)].visible = input.checked;
    rerender();
  });

  $('#devReload').onclick = () => { DEV_STATE = null; navigate('devDashboard', { key: info.key }); };
  $('#devSave').onclick = async () => {
    const body = {
      placements: DEV_STATE.placements
        // Una colocación huérfana apunta a un widget que ya no existe: guardarla
        // la volvería a rechazar el backend, así que se descarta al guardar.
        .filter(p => !p.orphan)
        .map((p, index) => ({
          widget_key: p.widget_key, visible: p.visible, position: (index + 1) * 10,
          size: p.size, title_override: p.title_override, role_names: p.role_names || [], options: p.options || {}
        }))
    };
    try {
      const result = await api('/api/dev/dashboards/' + encodeURIComponent(DEV_STATE.key), { method: 'PUT', body });
      $('#devMsg').textContent = `Composición guardada: ${result.placements} widget(s).`;
      $('#devMsg').classList.add('ok');
    } catch (error) {
      $('#devMsg').textContent = error.message;
      $('#devMsg').classList.remove('ok');
    }
  };
}

// --- Tabla de vistas y arranque ---------------------------------------------

const VIEWS = {
  resumen, buscar,
  person, node, asset, transportUnit,
  people, attendance, epp, training, cases,
  transport, checklists, transportIncidents,
  assets, nodes, maintenance, inventory, evidence, closeout,
  imports, projects, roles, authority, catalogs, users, devDashboard, audit
};

async function afterLogin() {
  CONTEXT = await api('/api/me/context');
  const areaNames = (CONTEXT.areas || []).map(a => a.name).join(', ');
  $('#who').textContent = `${ME.display_name} · ${ME.roles.join(', ')}${areaNames ? ` · ${areaNames}` : ''}`;
  buildNav();
  navigate('resumen');
}

async function boot() {
  const version = await api('/api/health').catch(() => null);
  if (version?.version) $('#versionTag').textContent = 'Tracking Core · ' + version.version;
  const status = await api('/api/setup/status');
  if (status.needs_setup) return show('setup');
  try {
    ME = await api('/api/me');
    show('app');
    await afterLogin();
  } catch {
    show('login');
  }
}

$('#setupForm').onsubmit = async event => {
  event.preventDefault();
  const form = event.target;
  msg(form, '');
  try {
    await api('/api/setup/first-admin', { method: 'POST', body: Object.fromEntries(new FormData(form)) });
    show('login');
    msg($('#loginForm'), 'Administrador creado. Inicie sesión.', true);
  } catch (error) { msg(form, error.message); }
};

$('#loginForm').onsubmit = async event => {
  event.preventDefault();
  const form = event.target;
  try {
    await api('/api/auth/login', { method: 'POST', body: Object.fromEntries(new FormData(form)) });
    ME = await api('/api/me');
    show('app');
    await afterLogin();
  } catch (error) { msg(form, error.message); }
};

$('#logout').onclick = async () => {
  await api('/api/auth/logout', { method: 'POST' });
  ME = null;
  CONTEXT = null;
  show('login');
};

$('#globalSearch').onsubmit = event => {
  event.preventDefault();
  navigate('buscar', { q: $('#globalSearchInput').value });
};

$('#menuToggle').onclick = () => {
  $('#sidebar').classList.contains('open') ? closeMenu() : openMenu();
};
$('#scrim').onclick = closeMenu;

boot().catch(error => { console.error(error); show('login'); });
