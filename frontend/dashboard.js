
const API_URL = "http://127.0.0.1:5000";

const user = JSON.parse(localStorage.getItem("user") || "null");

let allEvents = [];
let selectedEventId = null;

const $ = id => document.getElementById(id);


// ==========================================
// AUTHENTICATION
// ==========================================

if (!user || user.role !== "volunteer") {
    alert("Please login using your volunteer account.");
    window.location.href = "index.html";
}


// ==========================================
// API HELPER
// ==========================================

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


// ==========================================
// HELPER FUNCTIONS
// ==========================================

function safeText(value) {
    return String(value ?? "N/A").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}


function formatDate(value) {

    if (!value) return "N/A";

    const date = new Date(value);

    return isNaN(date.getTime())
        ? "N/A"
        : date.toLocaleDateString("en-IN");
}


// ==========================================
// INITIALIZE VOLUNTEER
// ==========================================

function initializeVolunteer() {

    $("volunteerName").textContent = user.name || "Volunteer";

    $("volunteerAvatar").textContent =
        (user.name || "V").charAt(0).toUpperCase();

}


// ==========================================
// LOAD DASHBOARD
// ==========================================

async function loadDashboard() {

    try {

        const [stats, registrations, attendance, certificates] =
            await Promise.all([

                apiRequest("/api/volunteer/stats"),

                apiRequest("/api/volunteer/registrations"),

                apiRequest("/api/volunteer/attendance"),

                apiRequest("/api/volunteer/certificates")

            ]);

        $("totalRegistrations").textContent =
            stats.total_registrations ?? 0;

        $("pendingApplications").textContent =
            stats.pending_applications ?? 0;

        $("approvedApplications").textContent =
            stats.approved_applications ?? 0;

        $("totalCertificates").textContent =
            stats.total_certificates ?? 0;

       // Display registrations
displayRegistrations(
    Array.isArray(registrations)
        ? registrations
        : registrations.registrations || []
);

// Display attendance
displayAttendance(
    Array.isArray(attendance)
        ? attendance
        : attendance.attendance || []
);

// Display certificates
displayCertificates(
    Array.isArray(certificates)
        ? certificates
        : certificates.certificates || []
);

    } catch (error) {

        console.error("Dashboard error:", error);

        alert("Unable to load dashboard: " + error.message);

    }

}


// ==========================================
// LOAD EVENTS
// ==========================================

async function loadEvents() {

    try {

        const data = await apiRequest("/api/events");

        allEvents = Array.isArray(data) ? data : data.events || [];

        displayEvents(allEvents);

        await loadCategories();

    } catch (error) {

        console.error(error);

        $("eventsContainer").innerHTML =
            `<p>Unable to load events: ${safeText(error.message)}</p>`;

    }

}


// ==========================================
// LOAD EVENT CATEGORIES
// ==========================================

async function loadCategories() {

    try {

        const data = await apiRequest("/api/event-categories");

        const categories = data.categories || [];

        $("categoryFilter").innerHTML = `
            <option value="">All Categories</option>

            ${categories.map(category => `
                <option value="${category.category_id}">
                    ${safeText(category.category_name)}
                </option>
            `).join("")}
        `;

    } catch (error) {

        console.error("Category loading error:", error);

    }

}


// ==========================================
// DISPLAY EVENTS
// ==========================================

function displayEvents(events) {

    const container = $("eventsContainer");

    if (!events.length) {

        container.innerHTML = "<p>No upcoming events available.</p>";

        return;
    }

    container.innerHTML = events.map(event => {

        const isRegistered = event.is_registered === true;

        return `

            <div class="event-card">

                <span class="event-category">
                    ${safeText(event.category_name || "General")}
                </span>

                <h3>${safeText(event.event_name)}</h3>

                <p>${safeText(event.description)}</p>

                <p>📅 ${formatDate(event.event_date)}</p>

                <p>📍 ${safeText(event.location)}</p>

                <p>👥 Volunteer Limit: ${safeText(event.volunteer_limit)}</p>

                <p>⏳ Registration Deadline:
                    ${formatDate(event.registration_deadline)}
                </p>

                <button
                    class="primary-btn"
                    onclick="openEventDetails(${Number(event.event_id)})">

                    ${isRegistered ? "View Application" : "View Details"}

                </button>

            </div>

        `;

    }).join("");

}


// ==========================================
// SEARCH AND FILTER EVENTS
// ==========================================

function filterEvents() {

    const search = $("eventSearch").value.toLowerCase().trim();

    const category = $("categoryFilter").value;

    const filtered = allEvents.filter(event => {

        const matchesSearch =
            (event.event_name || "").toLowerCase().includes(search) ||
            (event.location || "").toLowerCase().includes(search);

        const matchesCategory =
            !category ||
            String(event.category_id) === String(category);

        return matchesSearch && matchesCategory;

    });

    displayEvents(filtered);

}


// ==========================================
// OPEN EVENT DETAILS
// ==========================================

async function openEventDetails(eventId) {

    const event = allEvents.find(
        item => Number(item.event_id) === Number(eventId)
    );

    if (!event) return;

    selectedEventId = eventId;

    $("modalEventName").textContent = event.event_name;

    $("eventDetails").innerHTML = `

        <p><strong>Description:</strong> ${safeText(event.description)}</p>

        <p><strong>Date:</strong> ${formatDate(event.event_date)}</p>

        <p><strong>Location:</strong> ${safeText(event.location)}</p>

        <p><strong>Volunteer Limit:</strong> ${safeText(event.volunteer_limit)}</p>

        <p><strong>Registration Deadline:</strong>
            ${formatDate(event.registration_deadline)}
        </p>

    `;

    const registered = event.is_registered === true;

    $("registerEventBtn").disabled = registered;

    $("registerEventBtn").textContent =
        registered ? "Already Registered" : "Register for Event";

    $("eventMessage").textContent = "";

    $("eventModal").classList.remove("hidden");

}


// ==========================================
// REGISTER FOR EVENT
// ==========================================

async function registerForEvent() {

    if (!selectedEventId) return;

    $("registerEventBtn").disabled = true;

    try {

        const result = await apiRequest("/api/register-event", {

            method: "POST",

            body: JSON.stringify({
                event_id: selectedEventId
            })

        });

        $("eventMessage").textContent = result.message;

        $("registerEventBtn").textContent = "Registered";

        await loadEvents();

        await loadDashboard();

    } catch (error) {

        $("eventMessage").textContent = error.message;

        $("registerEventBtn").disabled = false;

    }

}


// ==========================================
// CLOSE EVENT MODAL
// ==========================================

function closeEventModal() {

    $("eventModal").classList.add("hidden");

    selectedEventId = null;

}


// ==========================================
// DISPLAY REGISTRATIONS
// ==========================================

function displayRegistrations(registrations) {

    const table = $("registrationsTable");

    if (!registrations.length) {

        table.innerHTML = `
            <tr>
                <td colspan="3">You haven't registered for any events yet.</td>
            </tr>
        `;

        return;
    }

    table.innerHTML = registrations.map(item => `

        <tr>

            <td>${safeText(item.event_name)}</td>

            <td>${formatDate(item.registration_date)}</td>

            <td>
                <span class="status ${safeText(item.application_status)}">
                    ${safeText(item.application_status)}
                </span>
            </td>

        </tr>

    `).join("");

}


// ==========================================
// DISPLAY ATTENDANCE
// ==========================================

function displayAttendance(attendance) {

    const table = $("attendanceTable");

    if (!attendance.length) {

        table.innerHTML = `
            <tr>
                <td colspan="3">No attendance records available.</td>
            </tr>
        `;

        return;
    }

    table.innerHTML = attendance.map(item => `

        <tr>

            <td>${safeText(item.event_name)}</td>

            <td>${formatDate(item.attendance_date)}</td>

            <td>
                <span class="status ${safeText(item.attendance_status)}">
                    ${safeText(item.attendance_status)}
                </span>
            </td>

        </tr>

    `).join("");

}


// ==========================================
// DISPLAY CERTIFICATES
// ==========================================

function displayCertificates(certificates) {

    const container = $("certificatesContainer");

    if (!certificates.length) {

        container.innerHTML = `
            <p>No certificates earned yet. Complete volunteering events to earn certificates!</p>
        `;

        return;
    }

    container.innerHTML = certificates.map(certificate => `

        <div class="certificate-card">

            <h3>🏆 ${safeText(certificate.event_name)}</h3>

            <p>Certificate Number:
                ${safeText(certificate.certificate_number)}
            </p>

            <p>Issued: ${formatDate(certificate.issue_date)}</p>

            <button
                class="primary-btn"
                onclick="downloadCertificate('${safeText(certificate.certificate_number)}')">

                View Certificate

            </button>

        </div>

    `).join("");

}


// ==========================================
// VIEW CERTIFICATE
// ==========================================


async function downloadCertificate(certificateNumber) {
    try {
        const response = await fetch(
            `http://127.0.0.1:5000/api/volunteer/certificates/${encodeURIComponent(certificateNumber)}/download`,
            {
                method: "GET",
                credentials: "include"
            }
        );

        if (!response.ok) {
            const error = await response.json();
            alert(error.message || "Unable to download certificate.");
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.href = url;
        link.download = `VolunteerHub_${certificateNumber}.pdf`;

        document.body.appendChild(link);
        link.click();
        link.remove();

        window.URL.revokeObjectURL(url);

    } catch (error) {
        console.error("Certificate download error:", error);
        alert("Could not download certificate. Please try again.");
    }
}



// ==========================================
// LOGOUT
// ==========================================

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


// ==========================================
// NAVIGATION
// ==========================================

document.querySelectorAll(".nav-link").forEach(link => {

    link.addEventListener("click", () => {

        document.querySelectorAll(".nav-link").forEach(item => {
            item.classList.remove("active");
        });

        link.classList.add("active");

    });

});


// ==========================================
// BUTTON EVENTS
// ==========================================

$("eventSearch").addEventListener("input", filterEvents);

$("categoryFilter").addEventListener("change", filterEvents);

$("refreshEventsBtn").addEventListener("click", loadEvents);

$("refreshRegistrationsBtn").addEventListener("click", loadDashboard);

$("registerEventBtn").addEventListener("click", registerForEvent);

$("closeEventModal").addEventListener("click", closeEventModal);

$("cancelEventModal").addEventListener("click", closeEventModal);

$("logoutBtn").addEventListener("click", logout);


// ==========================================
// INITIALIZE
// ==========================================

if (user && user.role === "volunteer") {

    initializeVolunteer();

    loadDashboard();

    loadEvents();

}
