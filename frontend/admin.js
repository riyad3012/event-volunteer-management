
const API_URL = "http://127.0.0.1:5000";

const user = JSON.parse(localStorage.getItem("user") || "null");

let allEvents = [];
let registrationChart = null;
let eventChart = null;

const $ = (id) => document.getElementById(id);


// CHECK ADMIN LOGIN

if (!user || user.role !== "admin") {
    alert("Please login using your admin account.");
    window.location.href = "index.html";
}


// API HELPER

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.message || "Something went wrong.");
    }

    return data;
}


// MESSAGE

function showMessage(message, element = "dashboardMessage") {
    if ($(element)) {
        $(element).textContent = message;
    }
}


// SAFE TEXT

function safeText(value) {
    return String(value ?? "N/A").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}


// DATE FORMAT

function formatDate(value) {
    if (!value) return "N/A";

    const date = new Date(value);

    return isNaN(date.getTime())
        ? "N/A"
        : date.toLocaleDateString("en-IN");
}


// LOAD COMPLETE DASHBOARD

async function loadDashboard() {

    try {
        showMessage("Loading dashboard...");

        const [stats, users, events, registrations] =
            await Promise.all([
                apiRequest("/api/admin/stats"),
                apiRequest("/api/admin/users"),
                apiRequest("/api/admin/events"),
                apiRequest("/api/admin/registrations")
            ]);

        $("totalVolunteers").textContent =
            stats.total_volunteers ?? 0;

        $("totalOrganizers").textContent =
            stats.total_organizers ?? 0;

        $("totalEvents").textContent =
            stats.total_events ?? 0;

        $("totalRegistrations").textContent =
            stats.total_registrations ?? 0;

        allEvents = events.events || [];

        displayUsers(users.users || []);
        displayEvents(allEvents);
        displayRegistrations(registrations.registrations || []);

        showMessage("Dashboard loaded successfully.");

    } catch (error) {
        console.error(error);
        showMessage("Unable to load dashboard: " + error.message);
    }
}


// DISPLAY USERS

function displayUsers(users) {

    const table = $("volunteersTable");

    const filteredUsers = users.filter(
        item => item.role !== "admin"
    );

    if (filteredUsers.length === 0) {
        table.innerHTML = `
            <tr>
                <td colspan="4">No users found.</td>
            </tr>
        `;
        return;
    }

    table.innerHTML = filteredUsers.map(item => `
        <tr>
            <td>${safeText(item.name)}</td>
            <td>${safeText(item.email)}</td>
            <td>${safeText(item.phone)}</td>
            <td>${safeText(item.role)}</td>
        </tr>
    `).join("");
}


// DISPLAY EVENTS

function displayEvents(events) {

    const table = $("eventsTable");

    if (!events.length) {
        table.innerHTML = `
            <tr>
                <td colspan="6">No events found.</td>
            </tr>
        `;
        return;
    }

    table.innerHTML = events.map(event => `
        <tr>
            <td>${safeText(event.title || event.event_name)}</td>
            <td>${formatDate(event.event_date)}</td>
            <td>${safeText(event.location)}</td>
            <td>${safeText(event.volunteer_limit)}</td>
            <td>
                <span class="status ${safeText(event.status)}">
                    ${safeText(event.status)}
                </span>
            </td>
            <td>
                <button class="edit-btn"
                    onclick="editEvent(${Number(event.event_id)})">
                    Edit
                </button>

                <button class="delete-btn"
                    onclick="deleteEvent(${Number(event.event_id)})">
                    Cancel
                </button>
            </td>
        </tr>
    `).join("");
}


// OPEN CREATE EVENT FORM

async function openEventForm(event = null) {

    try {
        $("eventForm").reset();

        $("eventId").value = event ? event.event_id : "";

        $("modalTitle").textContent =
            event ? "Edit Event" : "Add New Event";

        const options = await apiRequest("/api/admin/event-options");

        $("categoryId").innerHTML = `
            <option value="">Select Category</option>
            ${(options.categories || []).map(category => `
                <option value="${category.category_id}">
                    ${safeText(category.category_name)}
                </option>
            `).join("")}
        `;

        $("organizationId").innerHTML = `
            <option value="">Select Organization</option>
            ${(options.organizations || []).map(org => `
                <option value="${org.organization_id}">
                    ${safeText(org.organization_name)}
                </option>
            `).join("")}
        `;

        if (event) {
            $("eventName").value = event.title || event.event_name;
            $("eventDescription").value = event.description || "";
            $("eventDate").value = event.event_date?.slice(0, 10) || "";
            $("eventLocation").value = event.location || "";
            $("volunteerLimit").value = event.volunteer_limit || "";
            $("registrationDeadline").value =
                event.registration_deadline?.slice(0, 10) || "";

            $("categoryId").value = event.category_id;
            $("organizationId").value = event.organization_id;
        }

        $("eventModal").classList.remove("hidden");

    } catch (error) {
        showMessage(error.message);
    }
}


// CLOSE EVENT FORM

function closeEventForm() {
    $("eventModal").classList.add("hidden");
}


// CREATE OR UPDATE EVENT

async function saveEvent(event) {

    event.preventDefault();

    const eventId = $("eventId").value;

    const eventData = {
        event_name: $("eventName").value.trim(),
        description: $("eventDescription").value.trim(),
        event_date: $("eventDate").value,
        location: $("eventLocation").value.trim(),
        volunteer_limit: $("volunteerLimit").value,
        registration_deadline: $("registrationDeadline").value,
        category_id: $("categoryId").value,
        organization_id: $("organizationId").value
    };

    try {

        const endpoint = eventId
            ? `/api/admin/events/${eventId}`
            : "/api/admin/events";

        const method = eventId ? "PUT" : "POST";

        const result = await apiRequest(endpoint, {
            method: method,
            body: JSON.stringify(eventData)
        });

        closeEventForm();

        alert(result.message);

        await loadDashboard();

    } catch (error) {
        showMessage(error.message, "formMessage");
    }
}


// EDIT EVENT

function editEvent(eventId) {

    const event = allEvents.find(
        item => Number(item.event_id) === Number(eventId)
    );

    if (event) {
        openEventForm(event);
    }
}


// CANCEL EVENT

async function deleteEvent(eventId) {

    const confirmation = confirm(
        "Are you sure you want to cancel this event?"
    );

    if (!confirmation) return;

    try {

        const result = await apiRequest(
            `/api/admin/events/${eventId}`,
            { method: "DELETE" }
        );

        alert(result.message);

        await loadDashboard();

    } catch (error) {
        alert(error.message);
    }
}


// DISPLAY REGISTRATIONS

function displayRegistrations(registrations) {

    const table = $("registrationsTable");

    if (!registrations.length) {
        table.innerHTML = `
            <tr>
                <td colspan="5">No registrations found.</td>
            </tr>
        `;
        return;
    }

    table.innerHTML = registrations.map(item => {

        const status = item.application_status;

        return `
            <tr>
                <td>${safeText(item.user_name)}</td>
                <td>${safeText(item.event_name)}</td>
                <td>${formatDate(item.registration_date)}</td>
                <td>
                    <span class="status ${safeText(status)}">
                        ${safeText(status)}
                    </span>
                </td>
                <td>
                    ${status === "pending" ? `
                        <button class="approve-btn"
                            onclick="updateRegistration(${Number(item.registration_id)}, 'approved')">
                            Approve
                        </button>

                        <button class="reject-btn"
                            onclick="updateRegistration(${Number(item.registration_id)}, 'rejected')">
                            Reject
                        </button>
                    ` : "—"}
                </td>
            </tr>
        `;
    }).join("");
}


// APPROVE OR REJECT REGISTRATION

async function updateRegistration(id, status) {

    const confirmation = confirm(
        `Are you sure you want to ${status} this registration?`
    );

    if (!confirmation) return;

    try {

        const result = await apiRequest(
            `/api/admin/registrations/${id}/status`,
            {
                method: "PUT",
                body: JSON.stringify({ status })
            }
        );

        alert(result.message);

        await loadDashboard();

    } catch (error) {
        alert(error.message);
    }
}


// LOAD ANALYTICS

async function loadAnalytics() {

    try {

        const data = await apiRequest("/api/admin/analytics");

        if (!window.Chart) {
            showMessage("Chart library could not load.");
            return;
        }

        if (registrationChart) {
            registrationChart.destroy();
        }

        if (eventChart) {
            eventChart.destroy();
        }

        registrationChart = new Chart(
            $("registrationChart"),
            {
                type: "doughnut",

                data: {
                    labels: data.registrations.map(
                        item => item.status
                    ),

                    datasets: [{
                        label: "Registrations",
                        data: data.registrations.map(
                            item => item.total
                        )
                    }]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: true
                }
            }
        );


        eventChart = new Chart(
            $("eventChart"),
            {
                type: "bar",

                data: {
                    labels: data.events.map(
                        item => item.event_name
                    ),

                    datasets: [{
                        label: "Registrations",
                        data: data.events.map(
                            item => item.total
                        )
                    }]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        }
                    }
                }
            }
        );

    } catch (error) {
        showMessage("Analytics error: " + error.message);
    }
}


// LOGOUT

async function logout() {

    try {
        await apiRequest("/logout", {
            method: "POST"
        });
    } catch (error) {
        console.error(error);
    }

    localStorage.removeItem("user");

    window.location.href = "index.html";
}


// SIDEBAR NAVIGATION

document.querySelectorAll(".nav-link").forEach(link => {

    link.addEventListener("click", () => {

        document.querySelectorAll(".nav-link").forEach(item => {
            item.classList.remove("active");
        });

        link.classList.add("active");
    });

});


// BUTTON EVENTS

$("addEventBtn").addEventListener("click", () => {
    openEventForm();
});

$("closeModal").addEventListener("click", closeEventForm);

$("cancelModal").addEventListener("click", closeEventForm);

$("eventForm").addEventListener("submit", saveEvent);

$("refreshUsersBtn").addEventListener("click", loadDashboard);

$("refreshRegistrationsBtn").addEventListener("click", loadDashboard);

$("logoutBtn").addEventListener("click", logout);


// INITIALIZE DASHBOARD

if (user && user.role === "admin") {

    $("adminName").textContent = user.name || "Admin";

    loadDashboard();

    loadAnalytics();
}
