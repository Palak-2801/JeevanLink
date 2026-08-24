// ===================================================
// JEEVANLINK - BLOOD REQUEST FORM
// ===================================================

const REQUEST_API_URL = "/api/requests";


// ===================================================
// ELEMENTS
// ===================================================

const requestForm = document.getElementById("requestForm");

const formMessage = document.getElementById("formMessage");

const submitButton = document.getElementById("submitButton");

const submitButtonText = document.getElementById("submitButtonText");

const locationButton = document.getElementById("locationButton");

const locationButtonText = document.getElementById("locationButtonText");

const locationStatus = document.getElementById("locationStatus");

const latitudeInput = document.getElementById("latitude");

const longitudeInput = document.getElementById("longitude");

const resultPanel = document.getElementById("resultPanel");

const resultHeading = document.getElementById("resultHeading");

const resultSummary = document.getElementById("resultSummary");

const resultToken = document.getElementById("resultToken");

const matchList = document.getElementById("matchList");


// ===================================================
// HELPERS
// ===================================================

function showMessage(text, type) {

    formMessage.textContent = text;

    // "show" is what donar.css uses to reveal the box.
    formMessage.className = "form-message show " + type;
}


function hideMessage() {

    formMessage.className = "form-message";
}


function setFieldError(fieldId, message) {

    const errorElement = document.getElementById(fieldId + "Error");

    const field = document.getElementById(fieldId);

    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = message ? "block" : "none";
    }

    if (field) {
        field.classList.toggle("invalid", Boolean(message));
    }
}


function clearAllErrors() {

    const ids = [
        "requesterName",
        "requesterPhone",
        "bloodGroup",
        "units",
        "urgency",
        "hospital",
        "location"
    ];

    ids.forEach(function (id) {
        setFieldError(id, "");
    });
}


function getValue(id) {

    const element = document.getElementById(id);

    return element ? element.value.trim() : "";
}


// ===================================================
// PHONE - allow digits only
// ===================================================

const requesterPhoneInput = document.getElementById("requesterPhone");

requesterPhoneInput.addEventListener("input", function () {

    requesterPhoneInput.value =
        requesterPhoneInput.value.replace(/\D/g, "");
});


// ===================================================
// LOCATION
// ===================================================

locationButton.addEventListener("click", function () {

    if (!navigator.geolocation) {

        locationStatus.textContent =
            "Your browser does not support location services.";

        return;
    }

    locationButtonText.textContent = "Locating...";

    locationButton.disabled = true;

    locationStatus.textContent = "";

    navigator.geolocation.getCurrentPosition(

        function (position) {

            latitudeInput.value = position.coords.latitude.toFixed(6);

            longitudeInput.value = position.coords.longitude.toFixed(6);

            locationStatus.textContent =
                "Location set: " +
                latitudeInput.value +
                ", " +
                longitudeInput.value;

            locationButtonText.textContent = "Update location";

            locationButton.disabled = false;

            setFieldError("location", "");
        },

        function () {

            locationStatus.textContent =
                "Could not get your location. Allow location access in " +
                "the browser, or use the demo location button below.";

            locationButtonText.textContent = "Try again";

            locationButton.disabled = false;

            showDemoLocationOption();
        },

        {
            enableHighAccuracy: true,
            timeout: 10000
        }
    );
});


// Geolocation is often blocked on plain http. Offer demo
// coordinates as a fallback so the form is never a dead end.

function showDemoLocationOption() {

    if (document.getElementById("demoLocationButton")) {
        return;
    }

    const demoButton = document.createElement("button");

    demoButton.type = "button";

    demoButton.id = "demoLocationButton";

    demoButton.className = "location-button";

    demoButton.textContent = "Use demo location (Lucknow)";

    demoButton.addEventListener("click", function () {

        latitudeInput.value = "26.8500";

        longitudeInput.value = "80.9500";

        locationStatus.textContent =
            "Demo location set: 26.8500, 80.9500 (Lucknow)";

        setFieldError("location", "");
    });

    locationButton.parentNode.insertBefore(
        demoButton,
        locationStatus
    );
}


// ===================================================
// VALIDATION
// ===================================================

function validateForm() {

    clearAllErrors();

    let isValid = true;

    const name = getValue("requesterName");

    if (name.length < 3) {
        setFieldError("requesterName", "Enter your full name");
        isValid = false;
    }


    const phone = getValue("requesterPhone");

    if (phone.length !== 10 || !/^\d{10}$/.test(phone)) {
        setFieldError("requesterPhone", "Enter a valid 10-digit mobile number");
        isValid = false;
    }


    if (!getValue("bloodGroup")) {
        setFieldError("bloodGroup", "Select a blood group");
        isValid = false;
    }


    const units = Number(getValue("units"));

    if (!units || units < 1 || units > 10) {
        setFieldError("units", "Units must be between 1 and 10");
        isValid = false;
    }


    if (!getValue("urgency")) {
        setFieldError("urgency", "Select an urgency level");
        isValid = false;
    }


    if (getValue("hospital").length < 3) {
        setFieldError("hospital", "Enter the hospital name");
        isValid = false;
    }


    if (!latitudeInput.value || !longitudeInput.value) {
        setFieldError("location", "Use the location button to set the coordinates");
        showDemoLocationOption();
        isValid = false;
    }

    return isValid;
}


// ===================================================
// COLLECT DATA
// ===================================================

function collectFormData() {

    return {
        requesterName: getValue("requesterName"),
        requesterPhone: getValue("requesterPhone"),
        bloodGroup: getValue("bloodGroup"),
        bloodComponent: getValue("bloodComponent"),
        units: Number(getValue("units")),
        hospital: getValue("hospital"),
        urgency: getValue("urgency"),
        latitude: Number(latitudeInput.value),
        longitude: Number(longitudeInput.value)
    };
}


// ===================================================
// RESULT RENDER
// ===================================================

function renderResult(result) {

    resultPanel.hidden = false;

    resultHeading.textContent = "Request created successfully";

    resultSummary.textContent =
        result.matchesFound +
        " eligible donor(s) found. " +
        result.notifiedDonors.length +
        " have been alerted.";

    resultToken.textContent =
        "Request tracking link: " + result.responseUrl;

    matchList.innerHTML = "";

    if (result.notifiedDonors.length === 0) {

        const empty = document.createElement("p");

        empty.className = "location-status";

        empty.textContent =
            "No matching donors yet. To load demo donors, run " +
            "this in the terminal: python -m jeevanlink.seed_data";

        matchList.appendChild(empty);

        return;
    }

    result.notifiedDonors.forEach(function (donor) {

        const item = document.createElement("div");

        item.className = "information-item";

        const number = document.createElement("span");

        number.className = "item-number";

        number.textContent = String(donor.rank);

        const body = document.createElement("div");

        const heading = document.createElement("h2");

        heading.textContent = donor.name + "  (" + donor.bloodGroup + ")";

        const detail = document.createElement("p");

        detail.textContent =
            donor.distanceKm +
            " km away  ·  match score " +
            donor.score;

        body.appendChild(heading);

        body.appendChild(detail);

        item.appendChild(number);

        item.appendChild(body);

        matchList.appendChild(item);
    });

    resultPanel.scrollIntoView({ behavior: "smooth" });
}


// ===================================================
// SUBMIT
// ===================================================

requestForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    hideMessage();

    if (!validateForm()) {

        showMessage(
            "Some fields need attention. Please check above.",
            "error"
        );

        return;
    }

    submitButton.disabled = true;

    submitButtonText.textContent = "Creating request...";

    try {

        const response = await fetch(REQUEST_API_URL, {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(collectFormData())
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "Could not create the request.");
        }

        showMessage(
            "Request created. Nearby donors have been alerted.",
            "success"
        );

        renderResult(result);

        requestForm.reset();

        latitudeInput.value = "";

        longitudeInput.value = "";

        locationStatus.textContent = "";

        locationButtonText.textContent = "Use my current location";

    } catch (error) {

        showMessage(
            error.message ||
            "Could not reach the server. Is the backend running?",
            "error"
        );

    } finally {

        submitButton.disabled = false;

        submitButtonText.textContent = "Create request & alert donors";
    }
});
