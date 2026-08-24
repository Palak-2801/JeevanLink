// ===================================================
// JEEVANLINK - DONOR RESPONSE PAGE
// ===================================================
//
// Opened from the link in the WhatsApp/SMS alert:
//     /respond/<public_token>?d=<donor_id>
//
// The token identifies the request, the query parameter identifies
// which donor is responding.

const pathParts = window.location.pathname.split("/");
const REQUEST_TOKEN = pathParts[pathParts.length - 1];

const DONOR_ID = new URLSearchParams(window.location.search).get("d");


// ===================================================
// ELEMENTS
// ===================================================

const pageHeading = document.getElementById("pageHeading");
const pageIntro = document.getElementById("pageIntro");
const formMessage = document.getElementById("formMessage");
const requestDetails = document.getElementById("requestDetails");
const actionRow = document.getElementById("actionRow");
const acceptButton = document.getElementById("acceptButton");
const declineButton = document.getElementById("declineButton");
const routeBox = document.getElementById("routeBox");
const routeDetails = document.getElementById("routeDetails");
const mapsLink = document.getElementById("mapsLink");


// ===================================================
// HELPERS
// ===================================================

function showMessage(text, type) {
    formMessage.textContent = text;
    formMessage.className = "form-message show " + type;
}


function hideMessage() {
    formMessage.className = "form-message";
}


function addRow(label, value, valueClass) {
    const row = document.createElement("div");
    row.className = "detail-row";

    const left = document.createElement("span");
    left.textContent = label;

    const right = document.createElement("strong");
    right.textContent = value;

    if (valueClass) {
        right.className = valueClass;
    }

    row.appendChild(left);
    row.appendChild(right);
    requestDetails.appendChild(row);
}


// ===================================================
// LOAD THE REQUEST
// ===================================================

async function loadRequest() {

    if (!REQUEST_TOKEN) {
        pageIntro.textContent = "This link is not valid.";
        return;
    }

    try {
        const response = await fetch("/api/requests/" + REQUEST_TOKEN);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "Request not found.");
        }

        render(result.request);

    } catch (error) {
        pageIntro.textContent = "";
        showMessage(error.message, "error");
    }
}


function render(request) {

    requestDetails.innerHTML = "";
    requestDetails.hidden = false;

    addRow("Blood group", request.blood_group);
    addRow("Units needed", request.units);
    addRow("Hospital", request.hospital);
    addRow("Status", request.status);

    const status = String(request.status || "").toLowerCase();

    if (status === "open" || status === "alerted") {

        pageHeading.textContent = "Someone nearby needs blood";
        pageIntro.textContent =
            "Please confirm whether you are able to donate. " +
            "Your phone number stays private until you accept.";

        if (DONOR_ID) {
            actionRow.hidden = false;
        } else {
            showMessage(
                "This link is missing the donor reference, so it cannot " +
                "record a response. Please use the link from your alert.",
                "error"
            );
        }

        return;
    }

    if (status === "accepted") {
        pageHeading.textContent = "This request is already accepted";
        pageIntro.textContent =
            "Another donor responded first. Thank you for checking.";
        loadRoute();
        return;
    }

    if (status === "fulfilled") {
        pageHeading.textContent = "This request is complete";
        pageIntro.textContent = "The patient has received the blood needed.";
        return;
    }

    pageHeading.textContent = "This request is closed";
    pageIntro.textContent = "No further action is needed.";
}


// ===================================================
// ACCEPT
// ===================================================

acceptButton.addEventListener("click", async function () {

    hideMessage();
    acceptButton.disabled = true;
    declineButton.disabled = true;
    acceptButton.textContent = "Confirming...";

    try {
        const response = await fetch(
            "/api/requests/" + REQUEST_TOKEN + "/accept",
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ donorId: Number(DONOR_ID) })
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "Could not accept the request.");
        }

        actionRow.hidden = true;
        pageHeading.textContent = "Thank you";
        pageIntro.textContent =
            "Your response is confirmed. The hospital route is below.";

        showMessage("You accepted this request.", "success");

        loadRoute();

    } catch (error) {
        showMessage(error.message, "error");
        acceptButton.disabled = false;
        declineButton.disabled = false;
        acceptButton.textContent = "I can donate";
    }
});


// ===================================================
// DECLINE
// ===================================================

declineButton.addEventListener("click", async function () {

    hideMessage();
    acceptButton.disabled = true;
    declineButton.disabled = true;

    try {
        await fetch(
            "/api/requests/" + REQUEST_TOKEN + "/decline",
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ donorId: Number(DONOR_ID) })
            }
        );

        actionRow.hidden = true;
        pageHeading.textContent = "Response recorded";
        pageIntro.textContent =
            "Thank you for letting us know. We are contacting the next donor.";

    } catch (error) {
        showMessage("Could not record your response.", "error");
        acceptButton.disabled = false;
        declineButton.disabled = false;
    }
});


// ===================================================
// ROUTE (only available once accepted)
// ===================================================

async function loadRoute() {

    try {
        const response = await fetch(
            "/api/requests/" + REQUEST_TOKEN + "/route"
        );

        if (!response.ok) {
            return;
        }

        const result = await response.json();
        const routing = result.routing;

        routeDetails.innerHTML = "";

        const lines = [
            ["Hospital", routing.hospital],
            ["Distance", routing.distanceKm + " km"],
            ["Estimated time", routing.etaMinutes + " min"]
        ];

        lines.forEach(function (pair) {
            const row = document.createElement("div");
            row.className = "detail-row";

            const left = document.createElement("span");
            left.textContent = pair[0];

            const right = document.createElement("strong");
            right.textContent = pair[1];

            row.appendChild(left);
            row.appendChild(right);
            routeDetails.appendChild(row);
        });

        mapsLink.href = routing.googleMapsUrl;
        routeBox.hidden = false;

    } catch (error) {
        // Route stays hidden; nothing else to do.
    }
}


loadRequest();
