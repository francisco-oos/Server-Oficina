/*
 * Server Oficina · administración extendida de perfiles y usuarios
 * ================================================================
 *
 * Relevo OpenAI R1 sobre 0.1.0-alpha.4.
 *
 * El backend alpha.3/alpha.4 ya permite editar permisos de perfiles
 * personalizados y cambiar los perfiles asignados a un usuario. La UI alpha.4
 * sólo exponía creación y cambio de área. Esta extensión reutiliza esos
 * endpoints sin duplicar las reglas de autorización.
 */
'use strict';

(() => {
  const BASE_ROLES = new Set([
    'ADMIN', 'OFFICE', 'HR', 'HSE', 'SUPERVISOR',
    'MATERIAL', 'TALLER', 'TRANSPORTE'
  ]);

  const selectedValues = select =>
    [...select.selectedOptions].map(option => option.value);

  function permissionOptions(permissions, selected, disabled = false) {
    const allowed = new Set(selected || []);
    return permissions.map(permission => `
      <label class="admin-permission">
        <input type="checkbox" value="${esc(permission.code)}"
          ${allowed.has(permission.code) ? 'checked' : ''}
          ${disabled ? 'disabled' : ''}>
        <span>
          <b>${esc(permission.code)}</b>
          <small>${esc(permission.description || '')}</small>
        </span>
      </label>`).join('');
  }

  async function rolesAdminEnhanced() {
    setTitle('Perfiles y permisos', 'ADMINISTRACIÓN');

    const [permissions, roleRows, areas] = await Promise.all([
      api('/api/permissions'),
      api('/api/roles'),
      api('/api/areas')
    ]);

    const roleAreas = await Promise.all(
      roleRows.map(role =>
        api('/api/roles/' + encodeURIComponent(role.name) + '/area'))
    );
    const areaOf = Object.fromEntries(roleAreas.map(item => [item.role, item]));

    $('#content').innerHTML = `
      <p class="muted view-hint">
        El <b>área</b> organiza la experiencia. Los <b>permisos</b> son la
        autorización real. Los perfiles base están protegidos; para una variante
        operacional cree un perfil personalizado.
      </p>

      <div class="panel">
        <h3>Crear perfil personalizado</h3>
        <form id="roleCreateOpenAI">
          <div class="formgrid three">
            <input name="name" placeholder="Nombre del perfil" required minlength="2">
            <input name="description" placeholder="Descripción">
            <select name="area_code">
              ${areas.map(area =>
                `<option value="${esc(area.code)}">${esc(area.name)}</option>`
              ).join('')}
            </select>
          </div>
          <div class="admin-permission-grid">
            ${permissionOptions(permissions, [])}
          </div>
          <button>Crear perfil</button>
          <div class="msg"></div>
        </form>
      </div>

      <div class="stack">
        ${roleRows.map(role => {
          const protectedRole = BASE_ROLES.has(role.name);
          const area = areaOf[role.name]?.area_code || 'GENERAL';
          return `
            <section class="panel admin-role-card" data-role-card="${esc(role.name)}">
              <div class="panel-head">
                <div>
                  <h3>${esc(role.name)}</h3>
                  <div class="muted small">
                    ${protectedRole
                      ? 'Perfil base protegido · sus permisos no se modifican desde aquí'
                      : 'Perfil personalizado editable'}
                  </div>
                </div>
                ${protectedRole ? badge('PROTEGIDO') : badge('EDITABLE', 'ok')}
              </div>

              <div class="formgrid">
                <label>Descripción
                  <input data-role-description value="${esc(role.description || '')}"
                    ${protectedRole ? 'disabled' : ''}>
                </label>
                <label>Área
                  <select data-role-area="${esc(role.name)}">
                    ${areas.map(item => `<option value="${esc(item.code)}"
                      ${item.code === area ? 'selected' : ''}>${esc(item.name)}</option>`
                    ).join('')}
                  </select>
                </label>
              </div>

              <div class="admin-permission-grid ${protectedRole ? 'is-disabled' : ''}">
                ${permissionOptions(permissions, role.permissions, protectedRole)}
              </div>

              ${protectedRole ? '' : `
                <button data-save-role="${esc(role.name)}">Guardar permisos del perfil</button>
                <div class="msg" data-role-msg="${esc(role.name)}"></div>`}
            </section>`;
        }).join('')}
      </div>`;

    $('#roleCreateOpenAI').onsubmit = async event => {
      event.preventDefault();
      const form = event.target;
      const values = Object.fromEntries(new FormData(form));
      const selectedPermissions = $$(
        '.admin-permission input[type="checkbox"]:checked', form
      ).map(input => input.value);

      try {
        const created = await api('/api/roles', {
          method: 'POST',
          body: {
            name: values.name,
            description: values.description || '',
            permissions: selectedPermissions
          }
        });
        await api('/api/roles/' + encodeURIComponent(created.name) + '/area', {
          method: 'PUT',
          body: { area_code: values.area_code }
        });
        navigate('roles');
      } catch (error) {
        msg(form, error.message);
      }
    };

    $$('[data-role-area]').forEach(select => {
      select.onchange = async () => {
        try {
          await api('/api/roles/' + encodeURIComponent(select.dataset.roleArea) + '/area', {
            method: 'PUT',
            body: { area_code: select.value }
          });
        } catch (error) {
          alert(error.message);
        }
      };
    });

    $$('[data-save-role]').forEach(button => {
      button.onclick = async () => {
        const roleName = button.dataset.saveRole;
        const card = button.closest('[data-role-card]');
        const feedback = card.querySelector('[data-role-msg]');
        const selectedPermissions = $$(
          '.admin-permission input[type="checkbox"]:checked', card
        ).map(input => input.value);
        const description = $('[data-role-description]', card).value;

        try {
          await api('/api/roles/' + encodeURIComponent(roleName), {
            method: 'PUT',
            body: {
              name: roleName,
              description,
              permissions: selectedPermissions
            }
          });
          feedback.textContent = 'Perfil actualizado.';
          feedback.classList.add('ok');
        } catch (error) {
          feedback.textContent = error.message;
          feedback.classList.remove('ok');
        }
      };
    });
  }

  async function usersAdminEnhanced() {
    setTitle('Usuarios', 'ADMINISTRACIÓN');

    const [users, roleRows] = await Promise.all([
      api('/api/users'),
      api('/api/roles')
    ]);

    const roleOptions = selected => {
      const current = new Set(selected || []);
      return roleRows.map(role => `
        <option value="${esc(role.name)}"
          ${current.has(role.name) ? 'selected' : ''}>${esc(role.name)}</option>`
      ).join('');
    };

    $('#content').innerHTML = `
      <div class="panel">
        <h3>Crear usuario</h3>
        <form id="userCreateOpenAI" class="formgrid">
          <input name="display_name" placeholder="Nombre" required>
          <input name="username" placeholder="Usuario" required minlength="3">
          <input name="password" type="password" minlength="10"
            placeholder="Contraseña (mín. 10)" required>
          <label>Perfiles
            <select id="newUserRoles" multiple size="${Math.min(Math.max(roleRows.length, 3), 8)}">
              ${roleOptions([])}
            </select>
          </label>
          <button class="wide">Crear usuario</button>
          <div class="msg wide"></div>
        </form>
      </div>

      <div class="stack">
        ${users.map(user => `
          <section class="panel admin-user-card" data-user-card="${esc(user.id)}">
            <div class="panel-head">
              <div>
                <h3>${esc(user.display_name)}</h3>
                <div class="muted small">${esc(user.username)}</div>
              </div>
              ${badge(user.active ? 'ACTIVO' : 'INACTIVO', user.active ? 'ok' : 'bad')}
            </div>
            <label>Perfiles efectivos
              <select data-user-roles multiple
                size="${Math.min(Math.max(roleRows.length, 3), 8)}">
                ${roleOptions(user.roles)}
              </select>
            </label>
            <button data-save-user-roles="${esc(user.id)}">Guardar perfiles</button>
            <div class="msg"></div>
          </section>`).join('')}
      </div>`;

    $('#userCreateOpenAI').onsubmit = async event => {
      event.preventDefault();
      const form = event.target;
      const body = Object.fromEntries(new FormData(form));
      const roles = selectedValues($('#newUserRoles'));

      if (!roles.length) {
        msg(form, 'Seleccione al menos un perfil.');
        return;
      }
      try {
        await api('/api/users', {
          method: 'POST',
          body: {
            username: body.username,
            display_name: body.display_name,
            password: body.password,
            roles
          }
        });
        navigate('users');
      } catch (error) {
        msg(form, error.message);
      }
    };

    $$('[data-save-user-roles]').forEach(button => {
      button.onclick = async () => {
        const card = button.closest('[data-user-card]');
        const roles = selectedValues($('[data-user-roles]', card));
        const feedback = $('.msg', card);

        if (!roles.length) {
          feedback.textContent = 'El usuario debe conservar al menos un perfil.';
          feedback.classList.remove('ok');
          return;
        }
        try {
          await api('/api/users/' + encodeURIComponent(button.dataset.saveUserRoles) + '/roles', {
            method: 'PUT',
            body: { roles }
          });
          feedback.textContent = 'Perfiles actualizados.';
          feedback.classList.add('ok');
        } catch (error) {
          feedback.textContent = error.message;
          feedback.classList.remove('ok');
        }
      };
    });
  }

  // Sólo sustituye dos vistas administrativas; no toca seguridad ni dominios.
  VIEWS.roles = rolesAdminEnhanced;
  VIEWS.users = usersAdminEnhanced;
})();
