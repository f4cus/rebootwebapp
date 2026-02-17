# /opt/rebootwebapp/app.py
# RebootWebApp - UI para reinicio de servicios Windows
# Streamlit + Ansible + Azure AD Authentication

import streamlit as st
import subprocess
import yaml
import json
import logging
import re
import msal
import requests
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuración ---
CONFIG_PATH = Path(__file__).parent / "config" / "services_windows.yml"
AUTH_CONFIG_PATH = Path(__file__).parent / "config" / "azure_auth.yml"
PLAYBOOK_RESTART = "/opt/ansible/playbooks/windows/restart_services.yml"
PLAYBOOK_STATUS = "/opt/ansible/playbooks/windows/check_services.yml"
INVENTORY_PATH = "/opt/ansible/inventories/prod/hosts"
LOG_PATH = Path(__file__).parent / "logs" / "reinicios.log"
LOGO_PATH = Path(__file__).parent / "static" / "logo.png"
ANSIBLE_TIMEOUT = 300
SEQUENTIAL_WAIT_SECONDS = 60

# --- Configurar logging ---
LOG_PATH.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# AZURE AD AUTHENTICATION
# ============================================================================

def load_auth_config():
    with open(AUTH_CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


def get_msal_app(auth_config):
    return msal.ConfidentialClientApplication(
        auth_config['client_id'],
        authority=f"https://login.microsoftonline.com/{auth_config['tenant_id']}",
        client_credential=auth_config['client_secret']
    )


def get_auth_url(auth_config, msal_app):
    return msal_app.get_authorization_request_url(
        scopes=auth_config['scope'],
        redirect_uri=auth_config['redirect_uri']
    )


def get_token_from_code(auth_config, msal_app, code):
    return msal_app.acquire_token_by_authorization_code(
        code,
        scopes=auth_config['scope'],
        redirect_uri=auth_config['redirect_uri']
    )


def get_user_info(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def check_user_in_group(access_token, group_id):
    headers = {'Authorization': f'Bearer {access_token}'}
    url = 'https://graph.microsoft.com/v1.0/me/memberOf'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        groups = response.json().get('value', [])
        for group in groups:
            if group.get('id') == group_id:
                return True
    return False


def check_authentication():
    auth_config = load_auth_config()
    msal_app = get_msal_app(auth_config)
    
    if 'user' in st.session_state and st.session_state.user:
        return True, st.session_state.user, None
    
    query_params = st.query_params
    if 'code' in query_params:
        code = query_params['code']
        result = get_token_from_code(auth_config, msal_app, code)
        
        if 'access_token' in result:
            user_info = get_user_info(result['access_token'])
            if user_info:
                is_authorized = check_user_in_group(
                    result['access_token'], 
                    auth_config['authorized_group_id']
                )
                
                user_email = user_info.get('mail') or user_info.get('userPrincipalName', '')
                
                if not is_authorized:
                    logger.warning(f"ACCESO DENEGADO | Usuario: {user_email}")
                    st.query_params.clear()
                    return False, None, "no_autorizado"
                
                st.session_state.user = {
                    'name': user_info.get('displayName', 'Usuario'),
                    'email': user_email,
                    'id': user_info.get('id', '')
                }
                st.query_params.clear()
                logger.info(f"LOGIN | Usuario: {st.session_state.user['email']}")
                return True, st.session_state.user, None
        else:
            logger.error(f"Error de autenticación: {result.get('error_description', 'Unknown error')}")
    
    return False, None, None


def show_login_page(auth_config, msal_app):
    st.set_page_config(page_title="Login - Reinicio de Servicios", page_icon="🔐", layout="centered")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=150)
        st.title("Reinicio de Servicios")
        st.markdown("---")
        st.markdown("### Iniciar sesión")
        st.markdown("Debe autenticarse con su cuenta corporativa para continuar.")
        auth_url = get_auth_url(auth_config, msal_app)
        st.link_button("🔐 Iniciar sesión con Microsoft", auth_url, use_container_width=True)
        st.markdown("---")
        st.caption("Solo usuarios autorizados")


def show_access_denied():
    st.set_page_config(page_title="Acceso Denegado", page_icon="🚫", layout="centered")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=150)
        st.title("Acceso Denegado")
        st.markdown("---")
        st.error("🚫 No tiene permisos para acceder a esta aplicación.")
        st.markdown("Contacte al equipo de Infraestructura para solicitar acceso.")
        if st.button("🔄 Intentar con otra cuenta"):
            st.session_state.clear()
            st.rerun()


# ============================================================================
# CONFIGURATION & SERVICE FUNCTIONS
# ============================================================================

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


def get_service_status(hostname, services):
    services_json = json.dumps(services)
    cmd = [
        "ansible-playbook", PLAYBOOK_STATUS,
        "-i", INVENTORY_PATH,
        "-e", f"target_host={hostname}",
        "-e", f'{{"services":{services_json}}}'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        status = {}
        pattern = r'"msg":\s*"([^|]+)\|(\w+)"'
        matches = re.findall(pattern, result.stdout)
        for svc_name, state in matches:
            status[svc_name] = state
        return status
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout consultando estado de {hostname}")
        return {svc: 'timeout' for svc in services}
    except Exception as e:
        logger.error(f"Error consultando estado de {hostname}: {e}")
        return {svc: 'error' for svc in services}


def get_all_status(servers):
    all_status = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for server in servers:
            svc_names = [s['name'] for s in server['services']]
            futures[executor.submit(get_service_status, server['hostname'], svc_names)] = server['hostname']
        for future in as_completed(futures):
            hostname = futures[future]
            all_status[hostname] = future.result()
    return all_status


def restart_service(hostname, services, user_email, grupo_nombre):
    services_json = json.dumps(services)
    cmd = [
        "ansible-playbook", PLAYBOOK_RESTART,
        "-i", INVENTORY_PATH,
        "-e", f"target_host={hostname}",
        "-e", f'{{"services":{services_json}}}'
    ]
    logger.info(f"INICIO | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | Servicios: {services}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=ANSIBLE_TIMEOUT)
        if result.returncode == 0:
            logger.info(f"EXITO | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | Servicios: {services}")
            return True, hostname
        else:
            logger.error(f"FALLO | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | RC: {result.returncode}")
            return False, hostname
    except Exception as e:
        logger.error(f"ERROR | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | {e}")
        return False, hostname


def restart_single_service(hostname, service_name, user_email, grupo_nombre):
    services_json = json.dumps([service_name])
    cmd = [
        "ansible-playbook", PLAYBOOK_RESTART,
        "-i", INVENTORY_PATH,
        "-e", f"target_host={hostname}",
        "-e", f'{{"services":{services_json}}}'
    ]
    logger.info(f"INICIO | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | Servicio: {service_name}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=ANSIBLE_TIMEOUT)
        if result.returncode == 0:
            logger.info(f"EXITO | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | Servicio: {service_name}")
            return True, hostname, service_name
        else:
            logger.error(f"FALLO | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | Servicio: {service_name} | RC: {result.returncode}")
            return False, hostname, service_name
    except Exception as e:
        logger.error(f"ERROR | Grupo: {grupo_nombre} | Usuario: {user_email} | Servidor: {hostname} | Servicio: {service_name} | {e}")
        return False, hostname, service_name


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_status_table(servers, status_data):
    running_states = ['running', 'started']
    stopped_states = ['stopped']
    
    table_data = []
    for server in servers:
        hostname = server['hostname']
        server_status = status_data.get(hostname, {})
        for svc in server['services']:
            state = server_status.get(svc['name'], 'unknown').lower()
            if state in running_states:
                status_text = '🟢 Running'
            elif state in stopped_states:
                status_text = '🔴 Stopped'
            else:
                status_text = f'🟡 {state.capitalize()}'
            table_data.append({
                'Servidor': server['display_name'],
                'Servicio': svc['display_name'],
                'Estado': status_text
            })
    
    import pandas as pd
    df = pd.DataFrame(table_data)
    df.index = df.index + 1
    st.table(df)


def get_services_summary(servers):
    summary = []
    for server in servers:
        for svc in server['services']:
            summary.append(f"• {server['display_name']} → {svc['display_name']}")
    return summary


def show_guide():
    st.markdown("""
    ### 📖 Guía Rápida para Operadores
    
    **¿Qué hace esta aplicación?**
    
    Permite reiniciar servicios Windows de forma segura y controlada.
    
    ---
    
    **¿Cómo usarla?**
    
    1. **Seleccione la pestaña** correspondiente al grupo de servicios
    2. **Verifique el estado** de los servicios en la tabla:
       - 🟢 Running = Funcionando correctamente
       - 🔴 Stopped = Detenido
       - 🟡 Otro estado = Requiere atención
    3. **Haga clic en el botón de reinicio** (azul)
    4. **Confirme la operación** en el popup que aparece
    5. **Espere** mientras se muestra el progreso del reinicio
    6. **Verifique** que todos los servicios vuelvan a 🟢 Running
    
    ---
    
    **Opciones de reinicio:**
    
    | Modo | Descripción | Cuándo usarlo |
    |------|-------------|---------------|
    | **Paralelo** (por defecto) | Reinicia todos los servicios simultáneamente | Urgencias |
    | **Secuencial** | Reinicia un servicio por vez con espera entre cada uno | Reinicios controlados |
    
    Para usar modo secuencial, marque la casilla antes de presionar el botón de reinicio.
    
    ---
    
    **¿Qué hacer si algo falla?**
    
    1. ❌ **No reintente inmediatamente**
    2. ⏳ Espere 2-3 minutos
    3. 🔃 Presione "Refrescar estado" para verificar
    4. 📞 Si el problema persiste, contacte a Infraestructura
    """)


@st.dialog("⚠️ Confirmar Reinicio")
def show_restart_dialog(grupo, servers, user, sequential_mode):
    services_summary = get_services_summary(servers)
    total_services = len(services_summary)
    total_servers = len(servers)
    
    st.markdown(f"Está por reiniciar **{total_services} servicios** en **{total_servers} servidores**.")
    
    with st.expander("Ver detalle de servicios", expanded=False):
        for item in services_summary:
            st.markdown(item)
    
    st.warning("**Esta acción puede afectar a usuarios conectados.**")
    
    col_cancel, col_confirm = st.columns(2)
    
    with col_cancel:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()
    
    with col_confirm:
        if st.button("✅ Confirmar Reinicio", type="primary", use_container_width=True):
            st.session_state[f'execute_restart_{grupo["id"]}'] = True
            st.session_state[f'sequential_mode_{grupo["id"]}'] = sequential_mode
            st.rerun()


def execute_restart_with_status(servers, parallel, user_email, grupo_nombre, grupo_id):
    if parallel:
        with st.status("🔄 Reiniciando servicios en paralelo...", expanded=True) as status:
            st.write("Iniciando reinicio de todos los servidores simultáneamente...")
            
            results = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                for server in servers:
                    svc_names = [s['name'] for s in server['services']]
                    futures[executor.submit(restart_service, server['hostname'], svc_names, user_email, grupo_nombre)] = server['display_name']
                
                for future in as_completed(futures):
                    server_name = futures[future]
                    success, hostname = future.result()
                    results.append((success, hostname))
                    if success:
                        st.write(f"✅ {server_name} - Completado")
                    else:
                        st.write(f"❌ {server_name} - Error")
            
            success_count = sum(1 for r in results if r[0])
            total_count = len(results)
            
            if success_count == total_count:
                status.update(label="✅ Reinicio completado exitosamente", state="complete", expanded=False)
            else:
                status.update(label=f"⚠️ Reinicio con errores ({success_count}/{total_count})", state="error", expanded=True)
        
        return results
    
    else:
        all_services = []
        for server in servers:
            for svc in server['services']:
                all_services.append({
                    'hostname': server['hostname'],
                    'display_name': server['display_name'],
                    'service_name': svc['name'],
                    'service_display': svc['display_name']
                })
        
        total = len(all_services)
        results = []
        
        with st.status(f"🔄 Reiniciando servicios en secuencia (0/{total})...", expanded=True) as status:
            for idx, item in enumerate(all_services):
                status.update(label=f"🔄 Reiniciando servicio {idx+1}/{total}...")
                st.write(f"▶️ {item['display_name']} → {item['service_display']}")
                
                success, hostname, svc_name = restart_single_service(
                    item['hostname'], item['service_name'], user_email, grupo_nombre
                )
                results.append((success, hostname, svc_name))
                
                if success:
                    st.write(f"✅ Completado")
                else:
                    st.write(f"❌ Error")
                
                if idx < total - 1:
                    for remaining in range(SEQUENTIAL_WAIT_SECONDS, 0, -1):
                        status.update(label=f"⏳ Esperando {remaining}s antes del siguiente ({idx+1}/{total} completados)...")
                        time.sleep(1)
            
            success_count = sum(1 for r in results if r[0])
            
            if success_count == total:
                status.update(label="✅ Reinicio secuencial completado", state="complete", expanded=False)
            else:
                status.update(label=f"⚠️ Reinicio con errores ({success_count}/{total})", state="error", expanded=True)
        
        return results


def render_grupo_tab(grupo, user, config):
    grupo_id = grupo['id']
    servers = grupo['servers']
    
    # Inicializar estados
    status_key = f'status_data_{grupo_id}'
    refresh_key = f'last_refresh_{grupo_id}'
    execute_key = f'execute_restart_{grupo_id}'
    sequential_key = f'sequential_mode_{grupo_id}'
    guide_key = f'show_guide_{grupo_id}'
    
    if status_key not in st.session_state:
        st.session_state[status_key] = {}
    if refresh_key not in st.session_state:
        st.session_state[refresh_key] = None
    if execute_key not in st.session_state:
        st.session_state[execute_key] = False
    if guide_key not in st.session_state:
        st.session_state[guide_key] = False
    
    # Ejecutar reinicio si fue confirmado
    if st.session_state[execute_key]:
        st.session_state[execute_key] = False
        use_sequential = st.session_state.get(sequential_key, False)
        
        st.toast("🚀 Iniciando reinicio de servicios...", icon="🔄")
        
        results = execute_restart_with_status(
            servers, 
            parallel=not use_sequential, 
            user_email=user['email'],
            grupo_nombre=grupo['nombre'],
            grupo_id=grupo_id
        )
        
        with st.spinner("Actualizando estado..."):
            st.session_state[status_key] = get_all_status(servers)
            st.session_state[refresh_key] = datetime.now()
        
        success_count = sum(1 for r in results if r[0])
        total_count = len(results)
        if success_count == total_count:
            st.toast(f"✅ Reinicio completado: {success_count}/{total_count}", icon="✅")
        else:
            st.toast(f"⚠️ Reinicio con errores: {success_count}/{total_count}", icon="⚠️")
    
    # Botones de operación
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        restart_btn = st.button(
            f"🔄 {grupo['nombre_operacion']}", 
            type="primary", 
            use_container_width=True,
            key=f"restart_{grupo_id}"
        )
    
    with col2:
        refresh_btn = st.button(
            "🔃 Refrescar estado", 
            use_container_width=True,
            key=f"refresh_{grupo_id}"
        )
    
    with col3:
        guide_label = "📖 Ocultar instrucciones" if st.session_state[guide_key] else "📖 Instrucciones"
        if st.button(guide_label, use_container_width=True, key=f"guide_{grupo_id}"):
            st.session_state[guide_key] = not st.session_state[guide_key]
            st.rerun()
    
    sequential_mode = st.checkbox(
        "Reinicio secuencial - Un servicio cada 1 minuto", 
        value=False,
        key=f"sequential_{grupo_id}"
    )
    
    st.markdown("---")
    
    if st.session_state[guide_key]:
        show_guide()
        st.markdown("---")
    
    if refresh_btn or st.session_state[refresh_key] is None:
        with st.spinner("Consultando estado de servicios..."):
            st.session_state[status_key] = get_all_status(servers)
            st.session_state[refresh_key] = datetime.now()
    
    if st.session_state[refresh_key]:
        st.caption(f"Última actualización: {st.session_state[refresh_key].strftime('%H:%M:%S')}")
    
    render_status_table(servers, st.session_state[status_key])
    
    if restart_btn:
        show_restart_dialog(grupo, servers, user, sequential_mode)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    auth_config = load_auth_config()
    msal_app = get_msal_app(auth_config)
    
    is_authenticated, user, error = check_authentication()
    
    if error == "no_autorizado":
        show_access_denied()
        return
    
    if not is_authenticated:
        show_login_page(auth_config, msal_app)
        return
    
    st.set_page_config(
        page_title="Reinicio de Servicios",
        page_icon="🔄",
        layout="wide"
    )
    
    try:
        config = load_config()
    except Exception as e:
        st.error(f"Error cargando configuración: {e}")
        return
    
    # Header
    col_logo, col_title, col_user = st.columns([1, 3, 1])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=130)
    with col_title:
        st.markdown("<h2 style='margin-top: 20px;'>Reinicio de Servicios</h2>", unsafe_allow_html=True)
    with col_user:
        st.markdown(f"<div style='text-align: right; margin-top: 25px;'>👤 {user['name']}</div>", unsafe_allow_html=True)
        if st.button("Cerrar sesión", key="logout"):
            logger.info(f"LOGOUT | Usuario: {user['email']}")
            st.session_state.clear()
            st.rerun()
    
    st.markdown("---")
    
    # CSS para tabs
    st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        font-size: 1.2rem;
        font-weight: 600;
        padding: 12px 24px;
        background-color: #f0f2f6;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #007bff;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Tabs
    grupos = config['grupos']
    tab_labels = [f"{g['icono']} {g['nombre']}" for g in grupos]
    tabs = st.tabs(tab_labels)
    
    for idx, tab in enumerate(tabs):
        with tab:
            render_grupo_tab(grupos[idx], user, config)


if __name__ == "__main__":
    main()
