
const API_URL = "http://127.0.0.1:5000";

const user = JSON.parse(localStorage.getItem("user") || "null");

let allEvents = [];
let registrationChart = null;
let eventChart = null;

const $ = id => document.getElementById(id);


// ==========================================
// AUTHENTICATION
// ==========================================

if (!user || user.role !== "organizer") {
    alert("Please login using your organizer account.");
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
        throw new Error(
            data.message || data.error || "Something went wrong."
        );
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


function showMessage(message) {

    const element = $("formMessage");

    if (element) {
        element.textContent = message;
    }
}


// ==========================================
// LOAD ORGANIZER DASHBOARD
// ==========================================

async function loadDashboard() {

    try {

        const [stats, events, registrations] = await Promise.all([
            apiRequest("/api/organizer/stats"),
            apiRequest("/api/organizer/events"),
            apiRequest("/api/organizer/registrations")
        ]);

        $("totalEvents").textContent =
            stats.total_events ?? 0;

        $("totalRegistrations").textContent =
            stats.total_registrations ?? 0;

        $("pendingRegistrations").textContent =
            stats.pending_registrations ?? 0;

        $("approvedRegistrations").textContent =
            stats.approved_registrations ?? 0;

        allEvents = events.events || [];

        displayEvents(allEvents);

        displayRegistrations(registrations.registrations || []);

    } catch (error) {

        console.error("Dashboard error:", error);

        alert("Unable to load organizer dashboard: " + error.message);

    }
}


// ==========================================
// DISPLAY EVENTS
// ==========================================

function displayEvents(events) {

    const table = $("eventsTable");

    if (!events.length) {

        table.innerHTML = `
            <tr>
                <td colspan="6">No events created yet.</td>
            </tr>
        `;

        return;
    }

    table.innerHTML = events.map(event => `

        <tr>
            <td>${safeText(event.event_name)}</td>
            <td>${formatDate(event.event_date)}</td>
            <td>${safeText(event.location)}</td>
            <td>${safeText(event.volunteer_limit)}</td>

            <td>
                <span class="status ${safeText(event.status)}">
                    ${safeText(event.status)}
                </span>
            </td>

            <td>
                <button
                    class="edit-btn"
                    onclick="editEvent(${Number(event.event_id)})">
                    Edit
                </button>
            </td>
        </tr>

    `).join("");
}


// ==========================================
// DISPLAY REGISTRATIONS
// ==========================================

function displayRegistrations(registrations) {

    const table = $("registrationsTable");

    if (!registrations.length) {

        table.innerHTML = `
            <tr>
                <td colspan="6">No volunteer registrations found.</td>
            </tr>
        `;

        return;
    }

    table.innerHTML = registrations.map(item => {

        const status = item.application_status;

        return `

            <tr>
                <td>${safeText(item.volunteer_name)}</td>
                <td>${safeText(item.email)}</td>
                <td>${safeText(item.event_name)}</td>
                <td>${formatDate(item.registration_date)}</td>

                <td>
                    <span class="status ${safeText(status)}">
                        ${safeText(status)}
                    </span>
                </td>

                <td>
                    ${status === "pending" ? `

                        <button
                            class="approve-btn"
                            onclick="updateRegistration(${Number(item.registration_id)}, 'approved')">
                            Approve
                        </button>

                        <button
                            class="reject-btn"
                            onclick="updateRegistration(${Number(item.registration_id)}, 'rejected')">
                            Reject
                        </button>

                    ` : "—"}
                </td>
            </tr>

        `;

    }).join("");
}


// ==========================================
// OPEN CREATE EVENT MODAL
// ==========================================

async function openEventForm(event = null) {

    try {

        $("eventForm").reset();

        $("eventId").value = event ? event.event_id : "";

        $("modalTitle").textContent =
            event ? "Edit Event" : "Create Event";

        showMessage("");

        const options = await apiRequest(
            "/api/organizer/event-options"
        );

        $("categoryId").innerHTML = `
            <option value="">Select Category</option>

            ${(options.categories || []).map(category => `
                <option value="${category.category_id}">
                    ${safeText(category.category_name)}
                </option>
            `).join("")}
        `;

        if (event) {

            $("eventName").value = event.event_name || "";

            $("eventDescription").value =
                event.description || "";

            $("eventDate").value =
                event.event_date?.slice(0, 10) || "";

            $("eventLocation").value =
                event.location || "";

            $("volunteerLimit").value =
                event.volunteer_limit || "";

            $("registrationDeadline").value =
                event.registration_deadline?.slice(0, 10) || "";

            $("categoryId").value =
                event.category_id || "";
        }

        $("eventModal").classList.remove("hidden");

    } catch (error) {

        alert("Unable to open event form: " + error.message);

    }
}


// ==========================================
// CLOSE MODAL
// ==========================================

function closeEventForm() {
    $("eventModal").classList.add("hidden");
}


// ==========================================
// EDIT EVENT
// ==========================================

function editEvent(eventId) {

    const event = allEvents.find(
        item => Number(item.event_id) === Number(eventId)
    );

    if (event) {
        openEventForm(event);
    }
}


// ==========================================
// CREATE OR UPDATE EVENT
// ==========================================

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

        category_id: $("categoryId").value

    };

    try {

        const endpoint = eventId
            ? `/api/organizer/events/${eventId}`
            : "/api/organizer/events";

        const method = eventId ? "PUT" : "POST";

        const result = await apiRequest(endpoint, {
            method,
            body: JSON.stringify(eventData)
        });

        alert(result.message);

        closeEventForm();

        await loadDashboard();

        await loadAnalytics();

    } catch (error) {

        showMessage(error.message);

    }
}


// ==========================================
// APPROVE OR REJECT REGISTRATION
// ==========================================

async function updateRegistration(id, status) {

    const confirmation = confirm(
        `Are you sure you want to ${status} this volunteer?`
    );

    if (!confirmation) return;

    try {

        const result = await apiRequest(
            `/api/organizer/registrations/${id}/status`,
            {
                method: "PUT",
                body: JSON.stringify({ status })
            }
        );

        alert(result.message);

        await loadDashboard();

        await loadAnalytics();

        await loadAttendance();

        await loadCertificates();

    } catch (error) {

        alert(error.message);

    }
}


// ==========================================
// ATTENDANCE MANAGEMENT
// ==========================================

async function loadAttendance() {

    const table = $("attendanceTable");

    try {

        const data = await apiRequest(
            "/api/organizer/attendance"
        );

        const attendance = Array.isArray(data)
            ? data
            : data.attendance || [];

        displayAttendance(attendance);

    } catch (error) {

        console.error("Attendance error:", error);

        table.innerHTML = `
            <tr>
                <td colspan="5">
                    Unable to load attendance: ${safeText(error.message)}
                </td>
            </tr>
        `;
    }
}


function displayAttendance(attendance) {

    const table = $("attendanceTable");

    if (!attendance.length) {

        table.innerHTML = `
            <tr>
                <td colspan="5">
                    No approved volunteers available for attendance.
                </td>
            </tr>
        `;

        return;
    }

    table.innerHTML = attendance.map(item => {

        const status = item.attendance_status || "";

        return `

            <tr>
                <td>${safeText(item.volunteer_name)}</td>

                <td>${safeText(item.event_name)}</td>

                <td>${safeText(item.role_name || "Volunteer")}</td>

                <td>
                    <select id="attendance-${Number(item.registration_id)}">
                        <option value="">Select Status</option>
                        <option value="present" ${status === "present" ? "selected" : ""}>
                            Present
                        </option>
                        <option value="absent" ${status === "absent" ? "selected" : ""}>
                            Absent
                        </option>
                        <option value="late" ${status === "late" ? "selected" : ""}>
                            Late
                        </option>
                    </select>
                </td>

                <td>
                    <button
                        class="approve-btn"
                        onclick="saveAttendance(${Number(item.registration_id)})">
                        Save
                    </button>
                </td>
            </tr>

        `;

    }).join("");
}


async function saveAttendance(registrationId) {

    const select = $(`attendance-${registrationId}`);

    const attendanceStatus = select.value;

    if (!attendanceStatus) {
        alert("Please select an attendance status.");
        return;
    }

    try {

        const result = await apiRequest(
            `/api/organizer/attendance/${registrationId}`,
            {
                method: "PUT",
                body: JSON.stringify({
                    attendance_status: attendanceStatus
                })
            }
        );

        alert(result.message);

        await loadAttendance();

        await loadCertificates();

    } catch (error) {

        alert(error.message);

    }
}


// ==========================================
// CERTIFICATE MANAGEMENT
// ==========================================

async function loadCertificates() {

    const table = $("certificatesTable");

    try {

        const data = await apiRequest(
            "/api/organizer/certificates/eligible"
        );

        const certificates = Array.isArray(data)
            ? data
            : data.certificates || [];

        displayCertificates(certificates);

    } catch (error) {

        console.error("Certificate error:", error);

        table.innerHTML = `
            <tr>
                <td colspan="5">
                    Unable to load certificates: ${safeText(error.message)}
                </td>
            </tr>
        `;
    }
}


function displayCertificates(certificates) {

    const table = $("certificatesTable");

    if (!certificates.length) {

        table.innerHTML = `
            <tr>
                <td colspan="5">
                    No volunteers are eligible for certificates yet.
                </td>
            </tr>
        `;

        return;
    }

    table.innerHTML = certificates.map(item => {

        const generated = Boolean(item.certificate_code);

        return `

            <tr>
                <td>${safeText(item.volunteer_name)}</td>

                <td>${safeText(item.event_name)}</td>

                <td>
                    <span class="status present">Present</span>
                </td>

                <td>
                    ${generated
                        ? safeText(item.certificate_code)
                        : "Not generated"}
                </td>

                <td>
                    ${generated ? "Already Generated" : `

                        <button
                            class="approve-btn"
                            onclick="generateCertificate(${Number(item.registration_id)})">
                            Generate Certificate
                        </button>

                    `}
                </td>
            </tr>

        `;

    }).join("");
}


async function generateCertificate(registrationId) {

    const confirmation = confirm(
        "Generate a certificate for this volunteer?"
    );

    if (!confirmation) return;

    try {

        const result = await apiRequest(
            `/api/organizer/certificates/${registrationId}`,
            {
                method: "POST"
            }
        );

        alert(result.message);

        await loadCertificates();

    } catch (error) {

        alert(error.message);

    }
}


// ==========================================
// LOAD ANALYTICS
// ==========================================

async function loadAnalytics() {

    try {

        const data = await apiRequest(
            "/api/organizer/analytics"
        );

        if (!window.Chart) {
            console.error("Chart.js could not load.");
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

        console.error("Analytics error:", error);

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
// SIDEBAR NAVIGATION
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

$("addEventBtn").addEventListener("click", () => {
    openEventForm();
});

$("closeModal").addEventListener("click", closeEventForm);

$("cancelModal").addEventListener("click", closeEventForm);

$("eventForm").addEventListener("submit", saveEvent);

$("refreshRegistrationsBtn").addEventListener("click", loadDashboard);

$("refreshAttendanceBtn").addEventListener("click", loadAttendance);

$("refreshCertificatesBtn").addEventListener("click", loadCertificates);

$("logoutBtn").addEventListener("click", logout);


// ==========================================
// INITIALIZE DASHBOARD
// ==========================================

if (user && user.role === "organizer") {

    $("organizerName").textContent = user.name || "Organizer";

    loadDashboard();

    loadAnalytics();

    loadAttendance();

    loadCertificates();

}
