
const API_URL = "http://127.0.0.1:5000";

// PAGE SECTIONS
const loginSection = document.getElementById("loginSection");
const registerSection = document.getElementById("registerSection");
const roleSection = document.getElementById("roleSection");

const message = document.getElementById("message");
const registerMessage = document.getElementById("registerMessage");

let loggedInUser = null;


// ======================================
// SHOW AND HIDE SECTIONS
// ======================================

document.getElementById("registerLink").addEventListener("click", function(e) {
    e.preventDefault();

    loginSection.style.display = "none";
    registerSection.style.display = "block";
    registerMessage.textContent = "";
});

document.getElementById("loginLink").addEventListener("click", function(e) {
    e.preventDefault();

    registerSection.style.display = "none";
    loginSection.style.display = "block";
    message.textContent = "";
});


// ======================================
// SHOW ORGANIZATION NAME FIELD
// ======================================

const roleCheckboxes = document.querySelectorAll('input[name="roles"]');
const organizationName = document.getElementById("organizationName");
const organizationLabel = document.getElementById("organizationLabel");

roleCheckboxes.forEach(checkbox => {
    checkbox.addEventListener("change", function() {
        const organizerSelected = [...roleCheckboxes].some(
            item => item.checked && item.value === "organizer"
        );

        organizationName.style.display = organizerSelected ? "block" : "none";
        organizationLabel.style.display = organizerSelected ? "block" : "none";
        organizationName.required = organizerSelected;
    });
});


// ======================================
// USER REGISTRATION
// ======================================

document.getElementById("registerForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const name = document.getElementById("regName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const phone = document.getElementById("regPhone").value.trim();
    const password = document.getElementById("regPassword").value;

    const roles = [...roleCheckboxes]
        .filter(checkbox => checkbox.checked)
        .map(checkbox => checkbox.value);

    const orgName = organizationName.value.trim();

    if (roles.length === 0) {
        registerMessage.textContent = "Please select at least one role.";
        return;
    }

    if (roles.includes("organizer") && !orgName) {
        registerMessage.textContent = "Please enter your organization name.";
        return;
    }

    registerMessage.textContent = "Creating your account...";

    try {
        const response = await fetch(`${API_URL}/register`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name,
                email,
                phone,
                password,
                roles,
                organization_name: orgName
            })
        });

        const data = await response.json();

        if (response.ok) {
            registerMessage.textContent = "Account created successfully! Please login.";

            document.getElementById("registerForm").reset();

            organizationName.style.display = "none";
            organizationLabel.style.display = "none";
            organizationName.required = false;

            setTimeout(() => {
                registerSection.style.display = "none";
                loginSection.style.display = "block";
                document.getElementById("email").value = email;
                message.textContent = "Your account is ready. Please login.";
            }, 1200);

        } else {
            registerMessage.textContent = data.message || "Registration failed.";
        }

    } catch (error) {
        registerMessage.textContent = "Cannot connect to server!";
        console.error(error);
    }
});


// ======================================
// USER LOGIN
// ======================================

document.getElementById("loginForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    message.textContent = "Logging in...";

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.message || "Invalid login.";
            return;
        }

        loggedInUser = data;
        localStorage.setItem("user", JSON.stringify(data));

        // Admin gets the admin dashboard directly
        if (data.roles.includes("admin")) {
            await chooseDashboard("admin");
            return;
        }

        // Show role selection
        showRoleSelection(data.roles);

    } catch (error) {
        message.textContent = "Cannot connect to server!";
        console.error(error);
    }
});


// ======================================
// SHOW AVAILABLE DASHBOARDS
// ======================================

function showRoleSelection(roles) {
    loginSection.style.display = "none";
    registerSection.style.display = "none";
    roleSection.style.display = "block";

    const roleButtons = document.getElementById("roleButtons");
    roleButtons.innerHTML = "";

    roles.forEach(role => {
        const button = document.createElement("button");

        button.type = "button";
        button.textContent =
            role === "volunteer"
                ? "Continue as Volunteer"
                : "Continue as Organizer";

        button.addEventListener("click", () => chooseDashboard(role));

        roleButtons.appendChild(button);
    });
}


// ======================================
// SELECT DASHBOARD
// ======================================

async function chooseDashboard(role) {
    try {
        const response = await fetch(`${API_URL}/api/select-role`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ role })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Could not select dashboard.");
            return;
        }

        loggedInUser.role = role;
        localStorage.setItem("user", JSON.stringify(loggedInUser));

        if (role === "admin") {
            window.location.href = "admin.html";
        } else if (role === "organizer") {
            window.location.href = "organizer.html";
        } else if (role === "volunteer") {
            window.location.href = "dashboard.html";
        }

    } catch (error) {
        alert("Cannot connect to server!");
        console.error(error);
    }
}


// ======================================
// LOGOUT FROM ROLE SELECTION
// ======================================

document.getElementById("logoutFromRoles").addEventListener("click", async function() {
    try {
        await fetch(`${API_URL}/logout`, {
            method: "POST",
            credentials: "include"
        });
    } catch (error) {
        console.error(error);
    }

    localStorage.removeItem("user");
    loggedInUser = null;

    roleSection.style.display = "none";
    loginSection.style.display = "block";

    document.getElementById("loginForm").reset();
    message.textContent = "You have been logged out.";
});
