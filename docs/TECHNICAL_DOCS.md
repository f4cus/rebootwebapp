\# RebootWebApp - Documentación Técnica



\## Información General



| Campo | Valor |

|-------|-------|

| \*\*Nombre\*\* | RebootWebApp |

| \*\*Descripción\*\* | Aplicación web para reinicio controlado de servicios Windows |

| \*\*Stack\*\* | Python + Streamlit + Ansible + Azure AD |



---



\## 1. Arquitectura



```

┌─────────────────┐     HTTPS      ┌─────────────────┐     WinRM      ┌─────────────────┐

│   Navegador     │◄──────────────►│   Linux Server  │◄──────────────►│   Windows       │

│   (Operador)    │                │   (CentOS/RHEL) │                │   Servers       │

└─────────────────┘                │                 │                └─────────────────┘

&nbsp;                                  │  ┌───────────┐  │

&nbsp;                                  │  │  Nginx    │  │

&nbsp;                                  │  │  :443     │  │

&nbsp;                                  │  └─────┬─────┘  │

&nbsp;                                  │        │        │

&nbsp;                                  │  ┌─────▼─────┐  │

&nbsp;                                  │  │ Streamlit │  │

&nbsp;                                  │  │  :8501    │  │

&nbsp;                                  │  └─────┬─────┘  │

&nbsp;                                  │        │        │

&nbsp;                                  │  ┌─────▼─────┐  │

&nbsp;                                  │  │  Ansible  │  │

&nbsp;                                  │  └───────────┘  │

&nbsp;                                  └─────────────────┘

```



\### Componentes



| Componente | Función | Puerto |

|------------|---------|--------|

| Nginx | Reverse proxy con SSL | 443 |

| Streamlit | Interfaz web (Python) | 8501 (localhost) |

| Ansible | Automatización de reinicios vía WinRM | - |

| Azure AD | Autenticación y autorización | - |



---



\## 2. Estructura de Archivos



\### Aplicación Web

```

/opt/rebootwebapp/

├── app.py                          # Aplicación principal Streamlit

├── venv/                           # Virtual environment Python

├── config/

│   ├── services\_windows.yml        # Configuración de servidores y servicios

│   └── azure\_auth.yml              # Credenciales Azure AD (SENSIBLE)

├── static/

│   └── logo.png                    # Logo corporativo (opcional)

└── logs/

&nbsp;   └── reinicios.log               # Log de operaciones

```



\### Ansible

```

/opt/ansible/

├── ansible.cfg                     # Configuración global

├── inventories/

│   └── prod/

│       ├── hosts                   # Inventario de servidores

│       └── group\_vars/

│           └── windows.yml         # Credenciales WinRM (SENSIBLE)

└── playbooks/

&nbsp;   └── windows/

&nbsp;       ├── restart\_services.yml    # Playbook de reinicio

&nbsp;       └── check\_services.yml      # Playbook de consulta de estado

```



\### Nginx

```

/etc/nginx/

├── conf.d/

│   └── rebootwebapp.conf           # Configuración del sitio

└── ssl/

&nbsp;   ├── certificate.crt             # Certificado SSL

&nbsp;   └── certificate.key             # Clave privada (SENSIBLE)

```



---



\## 3. Configuración



\### 3.1 Archivo de servicios (services\_windows.yml)



```yaml

grupos:

&nbsp; - id: grupo\_id

&nbsp;   nombre: "Nombre del Grupo"

&nbsp;   icono: "🔄"

&nbsp;   nombre\_operacion: "Reiniciar Grupo"

&nbsp;   servers:

&nbsp;     - hostname: SERVER01.domain.local

&nbsp;       display\_name: "SERVER01"

&nbsp;       services:

&nbsp;         - name: ServiceTechnicalName

&nbsp;           display\_name: "Service Display Name"

```



\### 3.2 Agregar nuevo servidor



1\. Editar `/opt/rebootwebapp/config/services\_windows.yml`

2\. Agregar el servidor en el grupo correspondiente

3\. Editar `/opt/ansible/inventories/prod/hosts`

4\. Agregar el hostname al inventario

5\. Verificar conectividad:

&nbsp;  ```bash

&nbsp;  ansible SERVIDOR -i inventories/prod/hosts -m ansible.windows.win\_ping

&nbsp;  ```



\### 3.3 Agregar nuevo grupo/tab



Editar `services\_windows.yml` y agregar un nuevo bloque bajo `grupos:`:



```yaml

&nbsp; - id: nuevo\_grupo

&nbsp;   nombre: "Nuevo Grupo"

&nbsp;   icono: "🆕"

&nbsp;   nombre\_operacion: "Reiniciar Nuevo Grupo"

&nbsp;   servers:

&nbsp;     # ... servidores del grupo

```



---



\## 4. Credenciales y Accesos



\### 4.1 Ubicación de credenciales



| Credencial | Ubicación |

|------------|-----------|

| Usuario WinRM | `/opt/ansible/inventories/prod/group\_vars/windows.yml` |

| Azure AD Client Secret | `/opt/rebootwebapp/config/azure\_auth.yml` |

| Clave privada SSL | `/etc/nginx/ssl/` |



\### 4.2 Azure AD - Configuración requerida



1\. \*\*App Registration\*\* con los siguientes permisos (Microsoft Graph):

&nbsp;  - `User.Read`

&nbsp;  - `GroupMember.Read.All`



2\. \*\*Grupo de seguridad\*\* para autorizar usuarios



3\. \*\*Redirect URI\*\* configurado con HTTPS



\### 4.3 Gestión de usuarios



Para dar acceso a un nuevo operador:

1\. Azure Portal → Microsoft Entra ID → Groups

2\. Buscar el grupo autorizado

3\. Members → Add members



---



\## 5. Servicios del Sistema



\### 5.1 Servicio Streamlit



```bash

\# Ver estado

sudo systemctl status rebootwebapp



\# Reiniciar

sudo systemctl restart rebootwebapp



\# Ver logs del servicio

sudo journalctl -u rebootwebapp -f



\# Habilitar inicio automático

sudo systemctl enable rebootwebapp

```



\### 5.2 Nginx



```bash

\# Ver estado

sudo systemctl status nginx



\# Recargar configuración

sudo systemctl reload nginx



\# Probar configuración

sudo nginx -t

```



---



\## 6. Logs y Monitoreo



\### 6.1 Log de operaciones



```bash

\# Ver últimas operaciones

tail -50 /opt/rebootwebapp/logs/reinicios.log



\# Buscar operaciones de un usuario

grep "usuario@dominio.com" /opt/rebootwebapp/logs/reinicios.log



\# Buscar errores

grep "ERROR\\|FALLO" /opt/rebootwebapp/logs/reinicios.log

```



\### 6.2 Formato del log



```

TIMESTAMP | LEVEL | ACTION | Usuario: email | Servidor: hostname | Servicios: \[list]

```



Ejemplos:

```

2025-01-15 10:30:00 | INFO | LOGIN | Usuario: user@domain.com

2025-01-15 10:30:15 | INFO | INICIO | Grupo: GroupName | Usuario: user@domain.com | Servidor: SERVER01 | Servicios: \['Service1']

2025-01-15 10:30:45 | INFO | EXITO | Grupo: GroupName | Usuario: user@domain.com | Servidor: SERVER01 | Servicios: \['Service1']

2025-01-15 10:31:00 | ERROR | FALLO | Grupo: GroupName | Usuario: user@domain.com | Servidor: SERVER02 | RC: 2

```



---



\## 7. Troubleshooting



\### 7.1 La webapp no carga



```bash

\# Verificar servicio Streamlit

sudo systemctl status rebootwebapp



\# Verificar Nginx

sudo systemctl status nginx



\# Verificar puertos

ss -tlnp | grep -E "8501|443"



\# Ver logs de error

sudo journalctl -u rebootwebapp -n 50

```



\### 7.2 Error de autenticación Azure AD



1\. Verificar que el usuario pertenezca al grupo autorizado

2\. Verificar que el Client Secret no haya expirado

3\. Verificar el Redirect URI en Azure Portal

4\. Revisar logs: `tail -50 /opt/rebootwebapp/logs/reinicios.log`



\### 7.3 Servicios no se reinician



```bash

\# Probar conectividad WinRM

cd /opt/ansible

ansible SERVIDOR -i inventories/prod/hosts -m ansible.windows.win\_ping



\# Probar reinicio manual

ansible-playbook playbooks/windows/restart\_services.yml \\

&nbsp; -i inventories/prod/hosts \\

&nbsp; -e "target\_host=SERVIDOR" \\

&nbsp; -e '{"services":\["ServiceName"]}'

```



\### 7.4 Estado "Unknown" en servicios



\- Verificar nombre técnico del servicio (debe coincidir exactamente)

\- Verificar que el servidor esté en el inventario de Ansible

\- Verificar conectividad WinRM



---



\## 8. Mantenimiento



\### 8.1 Renovación de certificado SSL



```bash

\# Generar nuevo CSR

cd /etc/nginx/ssl

sudo openssl req -new -key certificate.key -out certificate.csr



\# Después de obtener el nuevo certificado

sudo cp nuevo\_certificado.crt /etc/nginx/ssl/certificate.crt

sudo systemctl reload nginx

```



\### 8.2 Renovación de Client Secret (Azure AD)



1\. Azure Portal → App registrations → Tu App

2\. Certificates \& secrets → New client secret

3\. Copiar el nuevo Value

4\. Actualizar `/opt/rebootwebapp/config/azure\_auth.yml`

5\. `sudo systemctl restart rebootwebapp`



\### 8.3 Rotación de logs



Crear `/etc/logrotate.d/rebootwebapp`:



```

/opt/rebootwebapp/logs/\*.log {

&nbsp;   weekly

&nbsp;   rotate 12

&nbsp;   compress

&nbsp;   missingok

&nbsp;   notifempty

}

```



---



\## 9. Requisitos



\### 9.1 Servidor Linux



\- CentOS/RHEL 9 o compatible

\- Python 3.9+

\- Ansible 2.14+

\- Nginx

\- Paquetes Python: streamlit, pyyaml, msal, requests, pywinrm, pandas



\### 9.2 Servidores Windows



\- WinRM habilitado

\- Puerto 5985 accesible desde el servidor Linux

\- Usuario de servicio con permisos para reiniciar los servicios



\### 9.3 Red



| Origen | Destino | Puerto | Protocolo |

|--------|---------|--------|-----------|

| Usuarios | Linux Server | 443 | HTTPS |

| Linux Server | Windows Servers | 5985 | WinRM |

| Linux Server | login.microsoftonline.com | 443 | HTTPS |

| Linux Server | graph.microsoft.com | 443 | HTTPS |



---



\## 10. Seguridad



\- ✅ Autenticación obligatoria via Azure AD

\- ✅ Autorización por grupo de seguridad

\- ✅ Credenciales en archivos separados (no en código)

\- ✅ HTTPS obligatorio

\- ✅ Logging completo de todas las operaciones

\- ⚠️ Considerar usar ansible-vault para credenciales WinRM

