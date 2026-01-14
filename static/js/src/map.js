window.initMap = async function () {
  const mapElement = document.getElementById("map");
  if (!mapElement) return;

  const position = { lat: 48.81193823595843, lng: 2.4044663369790507 };

  // Load the required libraries
  const { Map } = await google.maps.importLibrary("maps");
  const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

  const map = new Map(mapElement, {
    center: position,
    zoom: 16,
    disableDefaultUI: true,
    mapId: "7af81f7d5245a5e0b77c0a6b", // Map ID is required for AdvancedMarkerElement
  });

  // Create DOM element for the marker content
  const markerContent = document.createElement("div");
  markerContent.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50" width="60" height="60">
      <path fill="#151515" d="M25.015 2.4c-7.8 0-14.121 6.204-14.121 13.854 0 7.652 14.121 32.746 14.121 32.746 s14.122-25.094 14.122-32.746 c0-7.65-6.325-13.854-14.122-13.854z"/>
      <circle cx="25" cy="16" r="6" fill="#FFC845" />
    </svg>
    <div style="position: absolute; top: 40px; left: 50%; transform: translateX(-50%); font-weight: bold; font-size: 12px; color: #151515; white-space: nowrap;">Belle Vitesse</div>
  `;

  const marker = new AdvancedMarkerElement({
    map: map,
    position: position,
    content: markerContent,
    title: "Belle Vitesse"
  });

  marker.addListener("click", () => {
    const url = `https://www.google.com/maps?q=${position.lat},${position.lng}`;
    window.open(url, "_blank", "noopener");
  });
};
