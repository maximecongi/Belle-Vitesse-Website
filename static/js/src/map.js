function initMap() {
  const position = { lat: 48.81193823595843, lng: 2.4044663369790507 };

  const map = new google.maps.Map(document.getElementById("map"), {
    center: position,
    zoom: 16,
    disableDefaultUI: true,
    styles: [
      { featureType: "poi", stylers: [{ visibility: "off" }] },
      { featureType: "transit", stylers: [{ visibility: "off" }] },
      { featureType: "road", elementType: "labels", stylers: [{ visibility: "off" }] }
    ]
  });

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50">
      <path fill="#151515"
        d="M25.015 2.4c-7.8 0-14.121 6.204-14.121 13.854
           0 7.652 14.121 32.746 14.121 32.746
           s14.122-25.094 14.122-32.746
           c0-7.65-6.325-13.854-14.122-13.854z"/>
      <circle cx="25" cy="16" r="6" fill="#FFC845" />
    </svg>
  `;

  const marker = new google.maps.Marker({
    position: position,
    map: map,
    label: {
      text: "Belle Vitesse",
      color: "#151515",
      fontSize: "12px",
      fontWeight: "bold",
      position: "relative",
      top: "40px",
    },
    icon: {
      url: "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(60, 60),
      anchor: new google.maps.Point(30, 60),
      labelOrigin: new google.maps.Point(30, -20)
    }
  });

  marker.addListener("click", () => {
    const url = `https://www.google.com/maps?q=${position.lat},${position.lng}`;
    window.open(url, "_blank", "noopener");
  });
}

initMap();
