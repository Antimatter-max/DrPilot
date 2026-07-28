import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from qdrant_client import QdrantClient

from app.core.database import engine, Base
from app.api.v1.patient import router as patient_router
from app.api.v1.governance import router as governance_router
from app.api.v1.auth import router as auth_router
from app.services.rag_service import init_qdrant_guidelines

# 1. Initialize PostgreSQL database tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[DB Init Warning]: {str(e)}")

# 2. Instantiate FastAPI App
app = FastAPI(
    title="DrPilot API",
    description="Multimodal Clinical AI Assistant API",
    version="1.0.0"
)

# 3. Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. App Startup Events
@app.on_event("startup")
def startup_event():
    try:
        init_qdrant_guidelines()
    except Exception as e:
        print(f"[Startup Warning]: {str(e)}")

# 5. Mount API Routers under /api/v1 prefix
app.include_router(auth_router, prefix="/api/v1")
app.include_router(patient_router, prefix="/api/v1")
app.include_router(governance_router, prefix="/api/v1")

QDRANT_HOST = os.getenv("QDRANT_URL", "http://vector_db:6333")


@app.get("/admin", response_class=HTMLResponse)
def serve_admin_portal():
    """Serves the DrPilot Executive Admin Control Center with confirmation modals."""
    return """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>DrPilot - Executive Admin Portal</title>
      <script src="https://cdn.tailwindcss.com"></script>
      <link rel="stylesheet" href="https://rsms.me/inter/inter.css">
      <style>
        body { font-family: 'Inter', sans-serif; }
      </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen antialiased selection:bg-blue-500 selection:text-white">

      <!-- Top Navigation Header -->
      <header class="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur-md sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-lg">
              🛡️
            </div>
            <div>
              <h1 class="text-base font-semibold text-white tracking-tight">DrPilot Admin Control Center</h1>
              <p class="text-[11px] text-slate-400">PostgreSQL Identity & Access Management</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Database Online
            </span>
            <a href="http://localhost:3000" target="_blank" class="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700/80 transition shadow-sm flex items-center gap-1.5">
              <span>Launch App</span> ↗
            </a>
          </div>
        </div>
      </header>

      <!-- Main Container -->
      <main class="max-w-7xl mx-auto px-6 py-8 space-y-8">

        <!-- Metrics Overview Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Accounts</span>
              <span class="p-2 bg-blue-500/10 text-blue-400 rounded-lg text-sm">👥</span>
            </div>
            <p id="statTotalUsers" class="text-2xl font-bold text-white mt-2">0</p>
            <p class="text-[11px] text-slate-500 mt-1">Registered in system</p>
          </div>

          <div class="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Physicians & Surgeons</span>
              <span class="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg text-sm">🩺</span>
            </div>
            <p id="statPhysicians" class="text-2xl font-bold text-indigo-400 mt-2">0</p>
            <p class="text-[11px] text-slate-500 mt-1">Clinical access tier</p>
          </div>

          <div class="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">CMO & Governance</span>
              <span class="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg text-sm">🏛️</span>
            </div>
            <p id="statCMO" class="text-2xl font-bold text-emerald-400 mt-2">0</p>
            <p class="text-[11px] text-slate-500 mt-1">Administrative audit tier</p>
          </div>
        </div>

        <!-- Create User Form Card -->
        <section class="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl space-y-5">
          <div class="border-b border-slate-800/80 pb-4 flex items-center justify-between">
            <div>
              <h2 class="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                Provision New User Account
              </h2>
              <p class="text-xs text-slate-400 mt-0.5">Passwords are bcrypt hashed before committing to PostgreSQL storage.</p>
            </div>
          </div>

          <form id="addUserForm" onsubmit="promptCreateUser(event)" class="grid grid-cols-1 md:grid-cols-12 gap-4">
            <div class="md:col-span-3 space-y-1.5">
              <label class="block text-xs font-semibold text-slate-300">Full Name</label>
              <input type="text" id="fullName" placeholder="e.g. Dr. Alex Vance, MD" class="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/80 placeholder-slate-600 transition" required />
            </div>

            <div class="md:col-span-3 space-y-1.5">
              <label class="block text-xs font-semibold text-slate-300">Username</label>
              <input type="text" id="username" placeholder="e.g. dr.vance" class="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/80 placeholder-slate-600 transition" required />
            </div>

            <div class="md:col-span-2 space-y-1.5">
              <label class="block text-xs font-semibold text-slate-300">Password</label>
              <input type="password" id="password" placeholder="••••••••" class="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/80 placeholder-slate-600 transition" required />
            </div>

            <div class="md:col-span-2 space-y-1.5">
              <label class="block text-xs font-semibold text-slate-300">Access Class / Role</label>
              <select id="role" class="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-blue-300 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition">
                <option value="PHYSICIAN">Physician / Surgeon</option>
                <option value="CMO_GOVERNANCE">CMO / Governance</option>
              </select>
            </div>

            <div class="md:col-span-2 flex items-end">
              <button type="submit" id="submitBtn" class="w-full py-2.5 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold rounded-xl text-xs transition shadow-md shadow-blue-900/20">
                Create Account +
              </button>
            </div>
          </form>
        </section>

        <!-- User Directory Table Card -->
        <section class="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl space-y-5">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
            <div>
              <h2 class="text-sm font-bold uppercase tracking-wider text-white">
                Active User Directory
              </h2>
              <p class="text-xs text-slate-400 mt-0.5">Manage permissions or revoke credentials in real-time.</p>
            </div>

            <div class="flex items-center gap-3">
              <input type="text" id="searchInput" oninput="filterUsers()" placeholder="Search user or name..." class="px-3.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 placeholder-slate-600 w-52" />
              <button onclick="fetchUsers()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl border border-slate-700/80 transition flex items-center gap-1">
                <span>🔄</span> Refresh
              </button>
            </div>
          </div>

          <div class="overflow-x-auto rounded-xl border border-slate-800/80">
            <table class="w-full text-left text-xs text-slate-300">
              <thead class="bg-slate-950 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800/80 tracking-wider">
                <tr>
                  <th class="p-3.5">User Identity</th>
                  <th class="p-3.5">Username</th>
                  <th class="p-3.5">Access Role / Class</th>
                  <th class="p-3.5">Registered On</th>
                  <th class="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody id="userTableBody" class="divide-y divide-slate-800/60 bg-slate-950/40 font-mono text-[11px]">
                <tr>
                  <td colspan="5" class="p-6 text-center text-slate-500 italic">Loading active users...</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

      </main>

      <!-- Reusable Confirmation Modal Pop-Up -->
      <div id="confirmModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm hidden items-center justify-center z-50 p-4 transition-opacity">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl transform transition-all">
          <div class="flex items-center gap-3">
            <div id="modalIcon" class="w-10 h-10 rounded-xl flex items-center justify-center text-lg"></div>
            <div>
              <h3 id="modalTitle" class="text-sm font-bold text-white">Confirm Action</h3>
              <p id="modalSubtitle" class="text-[11px] text-slate-400">DrPilot Security Safeguard</p>
            </div>
          </div>
          <p id="modalDescription" class="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-800/60"></p>
          <div class="flex justify-end gap-2.5 pt-2">
            <button id="modalCancelBtn" onclick="closeModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl text-xs transition">
              Cancel
            </button>
            <button id="modalConfirmBtn" class="px-4 py-2 text-white font-semibold rounded-xl text-xs transition shadow-md">
              Confirm
            </button>
          </div>
        </div>
      </div>

      <!-- Floating Notification Toast -->
      <div id="toast" class="fixed bottom-6 right-6 hidden px-4 py-3 rounded-xl text-xs font-semibold shadow-2xl transition-all duration-300 transform translate-y-2 border z-50"></div>

      <script>
        const API_URL = 'http://localhost:8000/api/v1/auth';
        let allUsersCache = [];
        let pendingAction = null;

        function showToast(msg, isSuccess) {
          const toast = document.getElementById('toast');
          toast.className = `fixed bottom-6 right-6 px-4 py-3 rounded-xl text-xs font-semibold shadow-2xl transition-all duration-300 border z-50 ${
            isSuccess 
              ? 'bg-emerald-950 text-emerald-200 border-emerald-500/50' 
              : 'bg-red-950 text-red-200 border-red-500/50'
          }`;
          toast.innerText = msg;
          toast.classList.remove('hidden');
          setTimeout(() => toast.classList.add('hidden'), 3500);
        }

        function openModal({ icon, iconBg, title, description, confirmText, confirmBtnClass, onConfirm, onCancel }) {
          const modal = document.getElementById('confirmModal');
          const modalIcon = document.getElementById('modalIcon');
          const modalTitle = document.getElementById('modalTitle');
          const modalDescription = document.getElementById('modalDescription');
          const confirmBtn = document.getElementById('modalConfirmBtn');
          const cancelBtn = document.getElementById('modalCancelBtn');

          modalIcon.innerText = icon;
          modalIcon.className = `w-10 h-10 rounded-xl flex items-center justify-center text-lg ${iconBg}`;
          modalTitle.innerText = title;
          modalDescription.innerText = description;
          confirmBtn.innerText = confirmText;
          confirmBtn.className = `px-4 py-2 text-white font-semibold rounded-xl text-xs transition shadow-md ${confirmBtnClass}`;

          confirmBtn.onclick = () => {
            closeModal();
            onConfirm();
          };

          cancelBtn.onclick = () => {
            closeModal();
            if (onCancel) onCancel();
          };

          modal.classList.remove('hidden');
          modal.classList.add('flex');
        }

        function closeModal() {
          const modal = document.getElementById('confirmModal');
          modal.classList.add('hidden');
          modal.classList.remove('flex');
        }

        async function fetchUsers() {
          try {
            const res = await fetch(`${API_URL}/users`);
            const users = await res.json();
            allUsersCache = users;
            renderUsers(users);
            updateStats(users);
          } catch (e) {
            showToast('Failed to connect to FastAPI backend', false);
          }
        }

        function updateStats(users) {
          document.getElementById('statTotalUsers').innerText = users.length;
          document.getElementById('statPhysicians').innerText = users.filter(u => u.role === 'PHYSICIAN').length;
          document.getElementById('statCMO').innerText = users.filter(u => u.role === 'CMO_GOVERNANCE').length;
        }

        function renderUsers(users) {
          const tbody = document.getElementById('userTableBody');
          tbody.innerHTML = '';

          if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-500 italic">No matching user records found.</td></tr>';
            return;
          }

          users.forEach(u => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-900/60 transition';
            
            const initials = u.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            const isPhysician = u.role === 'PHYSICIAN';

            row.innerHTML = `
              <td class="p-3.5 font-sans">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-full ${isPhysician ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30' : 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'} flex items-center justify-center font-bold text-xs">
                    ${initials}
                  </div>
                  <div>
                    <p class="font-semibold text-slate-100 text-xs">${u.full_name}</p>
                    <p class="text-[10px] text-slate-500">ID #${u.id}</p>
                  </div>
                </div>
              </td>
              <td class="p-3.5 text-blue-400 font-medium">${u.username}</td>
              <td class="p-3.5 font-sans">
                <select onchange="promptRoleChange(this, ${u.id}, '${u.username}', '${u.role}')" class="px-2.5 py-1 bg-slate-900 border border-slate-700/80 rounded-lg text-xs font-semibold ${isPhysician ? 'text-indigo-300' : 'text-emerald-300'} focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer">
                  <option value="PHYSICIAN" ${u.role === 'PHYSICIAN' ? 'selected' : ''}>🩺 Physician / Surgeon</option>
                  <option value="CMO_GOVERNANCE" ${u.role === 'CMO_GOVERNANCE' ? 'selected' : ''}>🏛️ CMO / Governance</option>
                </select>
              </td>
              <td class="p-3.5 text-slate-400">${u.created_at}</td>
              <td class="p-3.5 text-right font-sans">
                <button onclick="promptDeleteUser(${u.id}, '${u.username}')" class="px-3 py-1 bg-red-950/60 hover:bg-red-900 text-red-200 border border-red-800/60 rounded-lg text-xs font-medium transition">
                  Remove 🗑️
                </button>
              </td>
            `;
            tbody.appendChild(row);
          });
        }

        function filterUsers() {
          const q = document.getElementById('searchInput').value.toLowerCase();
          const filtered = allUsersCache.filter(u => 
            u.full_name.toLowerCase().includes(q) || u.username.toLowerCase().includes(q)
          );
          renderUsers(filtered);
        }

        // CONFIRMATION POPUP 1: PROVISION USER
        function promptCreateUser(e) {
          e.preventDefault();
          const fullName = document.getElementById('fullName').value;
          const username = document.getElementById('username').value;
          const role = document.getElementById('role').value;

          openModal({
            icon: '👤',
            iconBg: 'bg-blue-600/20 text-blue-400 border border-blue-500/30',
            title: 'Confirm New User Creation',
            description: `Are you sure you want to provision account '${username}' (${fullName}) assigned as '${role}'?`,
            confirmText: 'Yes, Provision User',
            confirmBtnClass: 'bg-blue-600 hover:bg-blue-500',
            onConfirm: () => executeCreateUser()
          });
        }

        async function executeCreateUser() {
          const btn = document.getElementById('submitBtn');
          btn.innerText = 'Creating...';
          btn.disabled = true;

          const fullName = document.getElementById('fullName').value;
          const username = document.getElementById('username').value;
          const password = document.getElementById('password').value;
          const role = document.getElementById('role').value;

          try {
            const res = await fetch(`${API_URL}/register`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ full_name: fullName, username, password, role })
            });

            if (!res.ok) {
              const err = await res.json();
              throw new Error(err.detail || 'Failed to create user');
            }

            showToast(`User '${username}' successfully created`, true);
            document.getElementById('addUserForm').reset();
            fetchUsers();
          } catch (err) {
            showToast(err.message, false);
          } finally {
            btn.innerText = 'Create Account +';
            btn.disabled = false;
          }
        }

        // CONFIRMATION POPUP 2: CHANGE ROLE / CLASS
        function promptRoleChange(selectElem, userId, username, currentRole) {
          const newRole = selectElem.value;
          if (newRole === currentRole) return;

          openModal({
            icon: '🔄',
            iconBg: 'bg-amber-600/20 text-amber-400 border border-amber-500/30',
            title: 'Confirm Role Reclassification',
            description: `Are you sure you want to change '${username}' from '${currentRole}' to '${newRole}'? This changes their workspace permissions immediately.`,
            confirmText: 'Yes, Update Role',
            confirmBtnClass: 'bg-amber-600 hover:bg-amber-500',
            onConfirm: () => executeUpdateRole(userId, newRole),
            onCancel: () => {
              selectElem.value = currentRole; // Revert select on cancel
            }
          });
        }

        async function executeUpdateRole(userId, newRole) {
          try {
            const res = await fetch(`${API_URL}/users/${userId}/role`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ role: newRole })
            });

            if (res.ok) {
              showToast(`Role updated to ${newRole}`, true);
              fetchUsers();
            } else {
              throw new Error('Failed to update user role');
            }
          } catch (err) {
            showToast(err.message, false);
          }
        }

        // CONFIRMATION POPUP 3: REMOVE USER
        function promptDeleteUser(userId, username) {
          openModal({
            icon: '🗑️',
            iconBg: 'bg-red-600/20 text-red-400 border border-red-500/30',
            title: 'Confirm Account Removal',
            description: `Are you sure you want to permanently delete account '${username}' from the system? This action cannot be undone.`,
            confirmText: 'Delete Permanently',
            confirmBtnClass: 'bg-red-600 hover:bg-red-500',
            onConfirm: () => executeDeleteUser(userId, username)
          });
        }

        async function executeDeleteUser(userId, username) {
          try {
            const res = await fetch(`${API_URL}/users/${userId}`, { method: 'DELETE' });
            if (res.ok) {
              showToast(`Account '${username}' deleted`, true);
              fetchUsers();
            } else {
              throw new Error('Failed to delete account');
            }
          } catch (err) {
            showToast(err.message, false);
          }
        }

        window.onload = fetchUsers;
      </script>
    </body>
    </html>
    """


@app.get("/")
def read_root():
    return {"message": "DrPilot API Service is running."}


@app.get("/health")
def health_check():
    return {"status": "healthy"}