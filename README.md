# RebootWebApp 🔄

Aplicación web para reinicio controlado de servicios Windows, diseñada para operadores no técnicos (APB - A Prueba de Bobos).

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.33+-red.svg)
![Ansible](https://img.shields.io/badge/Ansible-2.14+-black.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Características

- **Interfaz simple**: Diseñada para usuarios no técnicos
- **Autenticación Azure AD**: Control de acceso mediante grupos de seguridad
- **Múltiples grupos de servicios**: Organización por tabs (Home Banking, Bantotal, etc.)
- **Dos modos de reinicio**:
  - **Paralelo**: Todos los servicios simultáneamente
  - **Secuencial**: Un servicio por vez con espera configurable
- **Feedback visual en tiempo real**: Progreso del reinicio con `st.status`
- **Confirmación de seguridad**: Popup antes de ejecutar acciones
- **Logging completo**: Auditoría de todas las operaciones
- **Escalable**: Fácil agregar nuevos servidores, servicios o grupos

## 📸 Screenshots

### Interfaz principal con tabs
```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo]   Reinicio de Servicios                    👤 Usuario    │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ 🌐 Home Banking  │  │ 🏦 Bantotal      │                     │
│  └──────────────────┘  └──────────────────┘                     │
├─────────────────────────────────────────────────────────────────┤
│  [🔄 Reiniciar]  [🔃 Refrescar]  [📖 Instrucciones]            │
│  ☐ Reinicio secuencial                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Servidor    │ Servicio         │ Estado                │    │
│  │ SERVER01    │ TomcatSRV        │ 🟢 Running            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## 🏗️ Arquitectura

```
┌─────────────┐     HTTPS     ┌─────────────────┐     WinRM     ┌─────────────┐
│  Navegador  │◄─────────────►│  Linux Server   │◄─────────────►│  Windows    │
│  (Usuario)  │               │  - Nginx        │               │  Servers    │
└─────────────┘               │  - Streamlit    │               └─────────────┘
                              │  - Ansible      │
      ┌───────────────────────┤                 │
      │ Azure AD              └─────────────────┘
      │ (Autenticación)
      └───────────────────────────────────────────
```

## 📋 Requisitos

### Servidor Linux (CentOS/RHEL 9)
- Python 3.9+
- Nginx
- Ansible 2.14+

### Servidores Windows
- WinRM habilitado
- Puerto 5985 accesible
- Usuario de servicio con permisos para reiniciar servicios

### Azure AD
- App Registration configurada
- Grupo de seguridad para autorización

## 🚀 Instalación

### 1. Clonar repositorio

```bash
git clone https://github.com/TU_USUARIO/rebootwebapp.git
cd rebootwebapp
```

### 2. Crear estructura de directorios

```bash
sudo mkdir -p /opt/rebootwebapp/{config,logs,static}
sudo mkdir -p /opt/ansible/{inventories/prod/group_vars,playbooks/windows}
```

### 3. Instalar dependencias Python

```bash
cd /opt/rebootwebapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Copiar archivos

```bash
# Webapp
cp webapp/app.py /opt/rebootwebapp/
cp webapp/config/*.example /opt/rebootwebapp/config/

# Ansible
cp ansible/playbooks/windows/*.yml /opt/ansible/playbooks/windows/
cp ansible/inventories/prod/hosts.example /opt/ansible/inventories/prod/hosts
cp ansible/inventories/prod/group_vars/*.example /opt/ansible/inventories/prod/group_vars/

# Renombrar archivos de ejemplo
cd /opt/rebootwebapp/config
mv services_windows.yml.example services_windows.yml
mv azure_auth.yml.example azure_auth.yml

cd /opt/ansible/inventories/prod/group_vars
mv windows.yml.example windows.yml
```

### 5. Configurar archivos

Editar los siguientes archivos con los valores reales:

- `/opt/rebootwebapp/config/services_windows.yml` - Servidores y servicios
- `/opt/rebootwebapp/config/azure_auth.yml` - Credenciales Azure AD
- `/opt/ansible/inventories/prod/hosts` - Inventario de servidores
- `/opt/ansible/inventories/prod/group_vars/windows.yml` - Credenciales WinRM

### 6. Configurar Nginx

```bash
sudo cp nginx/reinicios.conf.example /etc/nginx/conf.d/reinicios.conf
# Editar con los valores correctos (certificados, server_name)
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Configurar servicio systemd

```bash
sudo cp systemd/rebootwebapp.service /etc/systemd/system/
# Editar User/Group si es necesario
sudo systemctl daemon-reload
sudo systemctl enable rebootwebapp
sudo systemctl start rebootwebapp
```

### 8. Configurar WinRM en servidores Windows

```powershell
# Ejecutar como Administrador en cada servidor Windows
winrm quickconfig -q
winrm set winrm/config/service/auth '@{Basic="true"}'
winrm set winrm/config/service '@{AllowUnencrypted="true"}'
```

### 9. Verificar conectividad

```bash
cd /opt/ansible
ansible all -i inventories/prod/hosts -m ansible.windows.win_ping
```

## ⚙️ Configuración

### Agregar nuevo servidor

1. Editar `/opt/rebootwebapp/config/services_windows.yml`:
```yaml
grupos:
  - id: mi_grupo
    servers:
      - hostname: NUEVO_SERVER.dominio.com
        display_name: "NUEVO_SERVER"
        services:
          - name: NombreTecnicoServicio
            display_name: "Nombre Visible"
```

2. Agregar al inventario `/opt/ansible/inventories/prod/hosts`:
```ini
[windows]
NUEVO_SERVER.dominio.com
```

3. Verificar conectividad:
```bash
ansible NUEVO_SERVER.dominio.com -i inventories/prod/hosts -m ansible.windows.win_ping
```

### Agregar nuevo grupo/tab

Editar `/opt/rebootwebapp/config/services_windows.yml`:

```yaml
grupos:
  - id: nuevo_grupo
    nombre: "Nuevo Grupo"
    icono: "🆕"
    nombre_operacion: "Reiniciar Nuevo Grupo"
    servers:
      # ... servidores del grupo
```

## 📊 Logs

Los logs se almacenan en `/opt/rebootwebapp/logs/reinicios.log`:

```
2025-12-09 17:44:58 | INFO | LOGIN | Usuario: usuario@dominio.com
2025-12-09 17:49:14 | INFO | INICIO | Grupo: Home Banking | Usuario: usuario@dominio.com | Servidor: SERVER01 | Servicios: [...]
2025-12-09 17:49:38 | INFO | EXITO | Grupo: Home Banking | Usuario: usuario@dominio.com | Servidor: SERVER01 | Servicios: [...]
```

## 🔒 Seguridad

- Autenticación obligatoria via Azure AD
- Autorización por grupo de seguridad
- Credenciales en archivos separados (no en código)
- HTTPS obligatorio en producción
- Logging de todas las operaciones con usuario

## 🤝 Contribuir

1. Fork del repositorio
2. Crear branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 👨‍💻 Autor

Desarrollado por @f4cus

---

⭐ Si este proyecto te resultó útil, considera darle una estrella en GitHub.
