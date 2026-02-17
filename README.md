# RebootWebApp

Internal web application for controlled restart of Windows services in enterprise environments.

---

## Problem

In hybrid Windows environments, service restarts during incidents or maintenance are often handled manually.

Common patterns:

- RDP access to production servers  
- Manual service restarts  
- No structured execution order  
- No reliable execution trace  
- Excessive privilege exposure  

Over time, this creates operational risk, inconsistent procedures, and dependency on specific individuals.

The goal of this project was to reduce restart-related risk while preserving control, traceability, and access governance.

---

## Context

Designed for:

- Enterprise Windows server environments  
- Multi-service applications with service dependencies  
- Non-infrastructure operators  
- Audit-sensitive environments  
- Azure AD–based identity control  

Constraints:

- No direct RDP access for operators  
- Minimal privilege exposure  
- Clear operational logging  
- Controlled execution strategy (parallel vs sequential)  

This tool was built as an internal control layer, not as a generic automation framework.

---

## Solution Overview

RebootWebApp provides:

- Web-based restart interface  
- Azure AD authentication  
- Group-based authorization  
- Service restart orchestration via Ansible over WinRM  
- Execution mode selection (parallel or sequential)  
- Structured operation logging  

The design separates:

- Authentication  
- Request handling  
- Orchestration  
- Execution engine  

This reduces coupling between UI and infrastructure logic.

---

## Architecture and Design Decisions

### Streamlit

Selected because:

- Fast internal development  
- Minimal frontend complexity  
- Suitable for internal operational tools  

It is intentionally not positioned as a scalable public-facing platform.

### Ansible

Chosen for:

- Clear separation between orchestration and execution  
- Native WinRM support  
- Inventory-based host management  
- Idempotent execution model  

Direct PowerShell remoting from the web layer was avoided to prevent tight coupling and reduce risk surface.

### Execution Flow

1. User authenticates via Azure AD  
2. Group membership is validated  
3. Restart request is generated  
4. Ansible playbook executes against target hosts  
5. Results are logged with user and scope metadata  

---

## Operational Model

Two restart modes:

- **Parallel** — All services restart simultaneously  
- **Sequential** — Services restart in defined order with wait logic  

Sequential mode was introduced after observing cascading failures in multi-service applications when restarting in parallel.

Every execution records:

- Timestamp  
- User identity  
- Target host  
- Target services  
- Result code  

This supports audit review and post-incident analysis.

---

## Security Model

- Azure AD authentication via App Registration  
- Authorization via security group membership  
- No credentials stored in application code  
- WinRM service account isolated in Ansible inventory  
- HTTPS termination via Nginx  
- Full execution logging  

Planned improvement:

- Use of `ansible-vault` for credential encryption  

---

## Production Considerations

- Designed for internal network usage  
- Not internet-facing  
- Requires controlled WinRM exposure  
- Depends on accurate inventory management  
- Requires proper log rotation configuration  

Scalability:

- Suitable for small to medium service groups  
- Not designed for large-scale orchestration  
- No distributed execution model  

This is a controlled operational tool, not a fleet automation system.

---

## Lessons Learned

- Operators need guardrails more than flexibility.  
- Sequential restarts reduce risk in dependent systems.  
- Logging becomes critical months after incidents.  
- Decoupling UI from execution logic simplifies maintenance.  
- Identity-based authorization reduces access sprawl.  

---

## Limitations

- No scheduling capability  
- No automatic retry for partial failures  
- No granular RBAC beyond group membership  
- No native SIEM integration  
- Not built for zero-trust or public exposure scenarios  
