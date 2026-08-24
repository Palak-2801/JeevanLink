// ===================================================
// CONFIGURATION
// ===================================================

// true  = form data is kept in localStorage only (offline demo)
// false = form data is sent to the Flask API

const DEMO_MODE = false;


// Endpoint served by the Flask backend.

const DONOR_API_URL = "/api/donors";


// ===================================================
// ELEMENTS
// ===================================================

const donorForm = document.getElementById("donorForm");

const formMessage = document.getElementById(
    "formMessage"
);

const submitButton = document.getElementById(
    "submitButton"
);

const submitButtonText = document.getElementById(
    "submitButtonText"
);

const locationButton = document.getElementById(
    "locationButton"
);

const locationButtonText = document.getElementById(
    "locationButtonText"
);

const locationStatus = document.getElementById(
    "locationStatus"
);

const latitudeInput = document.getElementById(
    "latitude"
);

const longitudeInput = document.getElementById(
    "longitude"
);

const successOverlay = document.getElementById(
    "successOverlay"
);

const registeredDonorId = document.getElementById(
    "registeredDonorId"
);

const closeSuccessButton = document.getElementById(
    "closeSuccessButton"
);

const lastDonationDate = document.getElementById(
    "lastDonationDate"
);

const donationHint = document.getElementById(
    "donationHint"
);


// Maximum donation date should be today

const today = new Date();

lastDonationDate.max =
    today.toISOString().split("T")[0];


// ===================================================
// UTILITY FUNCTIONS
// ===================================================

function showFormMessage(type, message) {

    formMessage.className =
        `form-message show ${type}`;

    formMessage.textContent = message;

    formMessage.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
}


function hideFormMessage() {

    formMessage.className = "form-message";

    formMessage.textContent = "";
}


function showError(fieldId, message) {

    const field = document.getElementById(fieldId);

    const errorElement = document.getElementById(
        `${fieldId}Error`
    );

    if (field) {
        field.classList.add("invalid");
    }

    if (errorElement) {
        errorElement.textContent = message;
    }
}


function clearError(fieldId) {

    const field = document.getElementById(fieldId);

    const errorElement = document.getElementById(
        `${fieldId}Error`
    );

    if (field) {
        field.classList.remove("invalid");
    }

    if (errorElement) {
        errorElement.textContent = "";
    }
}


function clearAllErrors() {

    const fields = [
        "fullName",
        "phoneNumber",
        "email",
        "age",
        "bloodGroup",
        "lastDonationDate",
        "availability",
        "city",
        "location",
        "informationConsent"
    ];

    fields.forEach(function (fieldId) {
        clearError(fieldId);
    });

}


// ===================================================
// PHONE NUMBER: ONLY DIGITS
// ===================================================

const phoneNumberInput = document.getElementById(
    "phoneNumber"
);

phoneNumberInput.addEventListener(
    "input",
    function () {

        phoneNumberInput.value =
            phoneNumberInput.value.replace(/\D/g, "");

        clearError("phoneNumber");
    }
);


// ===================================================
// LIVE ERROR CLEARING
// ===================================================

const formFields = donorForm.querySelectorAll(
    "input, select"
);

formFields.forEach(function (field) {

    field.addEventListener(
        "input",
        function () {

            clearError(field.id);
            hideFormMessage();
        }
    );

    field.addEventListener(
        "change",
        function () {

            clearError(field.id);
            hideFormMessage();
        }
    );

});


// ===================================================
// LAST DONATION DATE INFORMATION
// ===================================================

lastDonationDate.addEventListener(
    "change",
    function () {

        clearError("lastDonationDate");

        if (!lastDonationDate.value) {

            donationHint.textContent =
                "Leave blank if you have never donated.";

            donationHint.style.color = "";

            return;
        }

        const selectedDate = new Date(
            lastDonationDate.value
        );

        const currentDate = new Date();

        const difference =
            currentDate.getTime() -
            selectedDate.getTime();

        const daysSinceDonation = Math.floor(
            difference / (1000 * 60 * 60 * 24)
        );

        if (daysSinceDonation < 0) {

            showError(
                "lastDonationDate",
                "Last donation date cannot be in the future."
            );

            return;
        }

        donationHint.textContent =
            `${daysSinceDonation} days since last donation. ` +
            "Final eligibility will be verified by the blood centre.";

        donationHint.style.color = "#167563";
    }
);


// ===================================================
// CURRENT LOCATION
// ===================================================

locationButton.addEventListener(
    "click",
    function () {

        clearError("location");

        if (!navigator.geolocation) {

            locationStatus.className =
                "location-status error";

            locationStatus.textContent =
                "Geolocation is not supported by this browser.";

            showError(
                "location",
                "Location could not be captured."
            );

            return;
        }


        locationButton.disabled = true;

        locationButtonText.textContent =
            "Getting Location...";

        locationStatus.className =
            "location-status";

        locationStatus.textContent =
            "Please allow location permission in your browser.";


        navigator.geolocation.getCurrentPosition(

            function (position) {

                const latitude =
                    position.coords.latitude;

                const longitude =
                    position.coords.longitude;

                latitudeInput.value =
                    latitude.toFixed(6);

                longitudeInput.value =
                    longitude.toFixed(6);

                locationStatus.className =
                    "location-status success";

                locationStatus.textContent =
                    `Location captured: ` +
                    `${latitude.toFixed(4)}, ` +
                    `${longitude.toFixed(4)}`;

                locationButton.disabled = false;

                locationButtonText.textContent =
                    "Location Captured ✓";
            },


            function (error) {

                let errorMessage =
                    "Unable to access your current location.";

                if (
                    error.code ===
                    error.PERMISSION_DENIED
                ) {
                    errorMessage =
                        "Location permission was denied.";
                }

                if (
                    error.code ===
                    error.POSITION_UNAVAILABLE
                ) {
                    errorMessage =
                        "Your current location is unavailable.";
                }

                if (
                    error.code ===
                    error.TIMEOUT
                ) {
                    errorMessage =
                        "Location request timed out.";
                }

                locationStatus.className =
                    "location-status error";

                locationStatus.textContent =
                    errorMessage;

                showError(
                    "location",
                    "Please allow location access."
                );

                locationButton.disabled = false;

                locationButtonText.textContent =
                    "Try Location Again";
            },


            {
                enableHighAccuracy: true,
                timeout: 12000,
                maximumAge: 60000
            }

        );

    }
);


// ===================================================
// FORM VALIDATION
// ===================================================

function validateForm() {

    clearAllErrors();

    let formIsValid = true;


    const fullName = document
        .getElementById("fullName")
        .value
        .trim();


    const phoneNumber = document
        .getElementById("phoneNumber")
        .value
        .trim();


    const email = document
        .getElementById("email")
        .value
        .trim();


    const age = Number(
        document.getElementById("age").value
    );


    const bloodGroup = document
        .getElementById("bloodGroup")
        .value;


    const availability = document
        .getElementById("availability")
        .value;


    const city = document
        .getElementById("city")
        .value
        .trim();


    const informationConsent =
        document
            .getElementById(
                "informationConsent"
            )
            .checked;


    // Full name validation

    if (fullName.length < 3) {

        showError(
            "fullName",
            "Please enter your complete name."
        );

        formIsValid = false;
    }


    // Phone validation

    if (!/^[6-9]\d{9}$/.test(phoneNumber)) {

        showError(
            "phoneNumber",
            "Enter a valid 10-digit Indian mobile number."
        );

        formIsValid = false;
    }


    // Email validation

    if (
        email &&
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    ) {

        showError(
            "email",
            "Enter a valid email address."
        );

        formIsValid = false;
    }


    // Age validation

    if (!age || age < 18 || age > 65) {

        showError(
            "age",
            "Age must be between 18 and 65."
        );

        formIsValid = false;
    }


    // Blood group validation

    if (!bloodGroup) {

        showError(
            "bloodGroup",
            "Please select your blood group."
        );

        formIsValid = false;
    }


    // Availability validation

    if (!availability) {

        showError(
            "availability",
            "Please select your availability."
        );

        formIsValid = false;
    }


    // City validation

    if (city.length < 3) {

        showError(
            "city",
            "Please enter your city or area."
        );

        formIsValid = false;
    }


    // Location validation

    if (
        !latitudeInput.value ||
        !longitudeInput.value
    ) {

        showError(
            "location",
            "Please capture your current location."
        );

        formIsValid = false;
    }


    // Consent validation

    if (!informationConsent) {

        showError(
            "informationConsent",
            "Please confirm the information and eligibility statement."
        );

        formIsValid = false;
    }


    return formIsValid;
}


// ===================================================
// COLLECT FORM DATA
// ===================================================

function collectFormData() {

    const availability =
        document.getElementById(
            "availability"
        ).value;


    return {
        name: document
            .getElementById("fullName")
            .value
            .trim(),

        phone: document
            .getElementById("phoneNumber")
            .value
            .trim(),

        email: document
            .getElementById("email")
            .value
            .trim(),

        age: Number(
            document.getElementById("age").value
        ),

        bloodGroup: document
            .getElementById("bloodGroup")
            .value,

        lastDonationDate:
            document
                .getElementById(
                    "lastDonationDate"
                )
                .value || null,

        availability: availability,

        available:
            availability !== "unavailable",

        urgentOnly:
            availability === "urgent-only",

        city: document
            .getElementById("city")
            .value
            .trim(),

        smsConsent:
            document
                .getElementById(
                    "smsConsent"
                )
                .checked,

        latitude: Number(
            latitudeInput.value
        ),

        longitude: Number(
            longitudeInput.value
        )
    };
}


// ===================================================
// DEMO MODE: LOCAL STORAGE
// ===================================================

function saveDonorInDemoMode(donorData) {

    const savedDonors = JSON.parse(
        localStorage.getItem("jeevanLinkDonors") ||
        "[]"
    );

    const donorId =
        `JL-${String(
            Date.now()
        ).slice(-6)}`;

    const newDonor = {
        id: donorId,
        ...donorData,
        verified: false,
        createdAt: new Date().toISOString()
    };

    savedDonors.push(newDonor);

    localStorage.setItem(
        "jeevanLinkDonors",
        JSON.stringify(savedDonors)
    );

    return {
        success: true,
        donorId: donorId,
        message:
            "Donor registered successfully."
    };
}


// ===================================================
// BACKEND API MODE
// ===================================================

async function saveDonorUsingAPI(donorData) {

    const response = await fetch(
        DONOR_API_URL,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify(donorData)
        }
    );


    const result = await response.json();


    if (!response.ok) {

        throw new Error(
            result.message ||
            "Unable to register donor."
        );
    }


    return result;
}


// ===================================================
// FORM SUBMISSION
// ===================================================

donorForm.addEventListener(
    "submit",
    async function (event) {

        event.preventDefault();

        hideFormMessage();


        const formIsValid = validateForm();


        if (!formIsValid) {

            showFormMessage(
                "error",
                "Please correct the highlighted fields."
            );

            return;
        }


        const donorData = collectFormData();


        submitButton.disabled = true;

        submitButtonText.textContent =
            "Registering Donor...";


        showFormMessage(
            "loading",
            "Creating your donor profile..."
        );


        try {

            let result;


            if (DEMO_MODE) {

                await new Promise(function (resolve) {
                    setTimeout(resolve, 700);
                });

                result =
                    saveDonorInDemoMode(donorData);

            } else {

                result =
                    await saveDonorUsingAPI(
                        donorData
                    );
            }


            showFormMessage(
                "success",
                result.message
            );


            openSuccessPopup(
                result.donorId
            );


        } catch (error) {

            showFormMessage(
                "error",
                error.message
            );

        } finally {

            submitButton.disabled = false;

            submitButtonText.textContent =
                "Register as Donor";
        }

    }
);


// ===================================================
// SUCCESS POPUP
// ===================================================

function openSuccessPopup(donorId) {

    registeredDonorId.textContent =
        donorId || "Registered";

    successOverlay.classList.add("open");

    successOverlay.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "popup-open"
    );
}


function closeSuccessPopup() {

    successOverlay.classList.remove("open");

    successOverlay.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "popup-open"
    );

    donorForm.reset();

    latitudeInput.value = "";
    longitudeInput.value = "";

    locationStatus.className =
        "location-status";

    locationStatus.textContent =
        "Location has not been captured.";

    locationButtonText.textContent =
        "Use My Current Location";

    donationHint.textContent =
        "Leave blank if you have never donated.";

    donationHint.style.color = "";

    hideFormMessage();

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


closeSuccessButton.addEventListener(
    "click",
    closeSuccessPopup
);


successOverlay.addEventListener(
    "click",
    function (event) {

        if (event.target === successOverlay) {
            closeSuccessPopup();
        }
    }
);


document.addEventListener(
    "keydown",
    function (event) {

        if (
            event.key === "Escape" &&
            successOverlay.classList.contains(
                "open"
            )
        ) {
            closeSuccessPopup();
        }
    }
);