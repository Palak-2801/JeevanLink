// ================= MOBILE NAVIGATION =================

const menuButton = document.getElementById("menuButton");
const navLinks = document.getElementById("navLinks");

menuButton.addEventListener("click", function () {
    const menuIsOpen = navLinks.classList.toggle("open");

    menuButton.classList.toggle("active", menuIsOpen);

    menuButton.setAttribute(
        "aria-expanded",
        String(menuIsOpen)
    );

    document.body.classList.toggle(
        "menu-open",
        menuIsOpen
    );
});


// Close menu after clicking a navigation link

const navigationItems = document.querySelectorAll(
    "#navLinks a"
);

navigationItems.forEach(function (link) {
    link.addEventListener("click", function () {
        navLinks.classList.remove("open");
        menuButton.classList.remove("active");

        menuButton.setAttribute(
            "aria-expanded",
            "false"
        );

        document.body.classList.remove("menu-open");
    });
});


// ================= MAP PREVIEW =================

const previewButtons = document.querySelectorAll(
    ".preview-button"
);

const mapArea = document.getElementById("mapArea");

const routeLabel = document.getElementById(
    "routeLabel"
);

const routeDistance = document.getElementById(
    "routeDistance"
);

const routeTime = document.getElementById(
    "routeTime"
);


// Preview data

const previewStates = {
    request: {
        label: "Critical O+ Request",
        distance: "City Care",
        time: "Created"
    },

    match: {
        label: "3 Eligible Donors",
        distance: "1.2 km",
        time: "Top Match"
    },

    route: {
        label: "Nearest Accepted Donor",
        distance: "2.4 km",
        time: "8 min"
    }
};


function updatePreview(stateName) {
    const state = previewStates[stateName];

    if (!state) {
        return;
    }

    mapArea.setAttribute(
        "data-current-state",
        stateName
    );

    routeLabel.textContent = state.label;
    routeDistance.textContent = state.distance;
    routeTime.textContent = state.time;

    previewButtons.forEach(function (button) {
        button.classList.toggle(
            "active",
            button.dataset.state === stateName
        );
    });
}


previewButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        updatePreview(button.dataset.state);
    });
});


// Default preview state

updatePreview("route");


// ================= SCROLL REVEAL ANIMATION =================

const revealElements = document.querySelectorAll(
    ".reveal"
);

if ("IntersectionObserver" in window) {

    const revealObserver = new IntersectionObserver(
        function (entries, observer) {

            entries.forEach(function (entry) {

                if (entry.isIntersecting) {
                    entry.target.classList.add("visible");

                    observer.unobserve(entry.target);
                }

            });

        },
        {
            threshold: 0.12
        }
    );

    revealElements.forEach(function (element) {
        revealObserver.observe(element);
    });

} else {

    // Fallback for old browsers

    revealElements.forEach(function (element) {
        element.classList.add("visible");
    });

}


// ================= CURRENT YEAR =================

const currentYear = document.getElementById(
    "currentYear"
);

// Guard against a missing element. Without this a null reference here
// throws, and every listener registered further down this file
// (Escape to close, close on resize) never gets attached.
if (currentYear) {
    currentYear.textContent = new Date().getFullYear();
}


// ================= ESCAPE KEY MENU CLOSE =================

document.addEventListener("keydown", function (event) {

    if (event.key === "Escape") {

        navLinks.classList.remove("open");

        menuButton.classList.remove("active");

        menuButton.setAttribute(
            "aria-expanded",
            "false"
        );

        document.body.classList.remove("menu-open");
    }

});


// ================= CLOSE MOBILE MENU ON RESIZE =================

window.addEventListener("resize", function () {

    if (window.innerWidth > 760) {

        navLinks.classList.remove("open");

        menuButton.classList.remove("active");

        menuButton.setAttribute(
            "aria-expanded",
            "false"
        );

        document.body.classList.remove("menu-open");
    }

});