const API_URL = "http://localhost:8000"; // backend FastAPI

let token = null;

// Elements
const loginSection = document.getElementById("login-section");
const signupSection = document.getElementById("signup-section");
const dashboard = document.getElementById("dashboard");
const userInfo = document.getElementById("user-info");

// Switch forms
document.getElementById("show-signup").onclick = () => {
  loginSection.classList.add("hidden");
  signupSection.classList.remove("hidden");
};
document.getElementById("show-login").onclick = () => {
  signupSection.classList.add("hidden");
  loginSection.classList.remove("hidden");
};

// Signup
document.getElementById("signup-form").onsubmit = async (e) => {
  e.preventDefault();
  const payload = {
    email: document.getElementById("signup-email").value,
    password: document.getElementById("signup-password").value,
    full_name: document.getElementById("signup-name").value,
    company_name: document.getElementById("signup-company").value,
    country: document.getElementById("signup-country").value,
  };
  const res = await fetch(API_URL + "/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    alert("Signup successful! Please log in.");
    signupSection.classList.add("hidden");
    loginSection.classList.remove("hidden");
  } else {
    alert("Signup failed.");
  }
};

// Login
document.getElementById("login-form").onsubmit = async (e) => {
  e.preventDefault();
  const formData = new URLSearchParams();
  formData.append("username", document.getElementById("login-email").value);
  formData.append("password", document.getElementById("login-password").value);

  const res = await fetch(API_URL + "/auth/token", {
    method: "POST",
    body: formData,
  });
  if (res.ok) {
    const data = await res.json();
    token = data.access_token;
    loginSection.classList.add("hidden");
    dashboard.classList.remove("hidden");
    loadDashboard();
  } else {
    alert("Login failed");
  }
};

// Logout
document.getElementById("logout").onclick = () => {
  token = null;
  dashboard.classList.add("hidden");
  loginSection.classList.remove("hidden");
};

// Submit expense
document.getElementById("expense-form").onsubmit = async (e) => {
  e.preventDefault();
  const formData = new FormData();
  formData.append("amount", document.getElementById("amount").value);
  formData.append("currency", document.getElementById("currency").value);
  formData.append("category", document.getElementById("category").value);
  formData.append("description", document.getElementById("description").value);
  const file = document.getElementById("receipt").files[0];
  if (file) formData.append("file", file);

  const res = await fetch(API_URL + "/expenses/", {
    method: "POST",
    headers: { Authorization: "Bearer " + token },
    body: formData,
  });
  if (res.ok) {
    alert("Expense submitted!");
    loadMyExpenses();
  } else {
    alert("Error submitting expense");
  }
};

// Load dashboard
async function loadDashboard() {
  loadMyExpenses();
  loadPendingApprovals();
}

// My expenses
async function loadMyExpenses() {
  const res = await fetch(API_URL + "/expenses/mine", {
    headers: { Authorization: "Bearer " + token },
  });
  const data = await res.json();
  const tbody = document.querySelector("#my-expenses tbody");
  tbody.innerHTML = "";
  data.forEach((exp) => {
    const row = `<tr>
      <td>${exp.id}</td>
      <td>${exp.amount}</td>
      <td>${exp.currency}</td>
      <td>${exp.status}</td>
      <td>${exp.description || ""}</td>
    </tr>`;
    tbody.insertAdjacentHTML("beforeend", row);
  });
}

// Pending approvals
async function loadPendingApprovals() {
  const res = await fetch(API_URL + "/expenses/pending", {
    headers: { Authorization: "Bearer " + token },
  });
  const data = await res.json();
  const tbody = document.querySelector("#pending-approvals tbody");
  tbody.innerHTML = "";
  data.forEach((exp) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${exp.id}</td>
      <td>${exp.amount}</td>
      <td>${exp.currency}</td>
      <td>${exp.description || ""}</td>
      <td>
        <button data-id="${exp.id}" data-action="approve">Approve</button>
        <button data-id="${exp.id}" data-action="reject">Reject</button>
      </td>`;
    tbody.appendChild(row);
  });

  // Attach handlers
  tbody.querySelectorAll("button").forEach((btn) => {
    btn.onclick = () => takeAction(btn.dataset.id, btn.dataset.action === "approve");
  });
}

// Approve/Reject
async function takeAction(expenseId, approved) {
  const res = await fetch(API_URL + `/expenses/${expenseId}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    body: JSON.stringify({ approved, comment: "" }),
  });
  if (res.ok) {
    alert("Action recorded");
    loadPendingApprovals();
    loadMyExpenses();
  } else {
    alert("Failed to take action");
  }
}
