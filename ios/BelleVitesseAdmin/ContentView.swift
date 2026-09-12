import SwiftUI

/// Vue principale de l'application iPad Belle Vitesse.
struct ContentView: View {
    @Binding var incomingURL: URL?
    @StateObject private var authManager = BiometricAuthManager()
    @AppStorage("bv_admin_server_url") private var serverURLString: String = "https://team.bellevitesse.com/admin"
    @AppStorage("bv_auto_lock_on_background") private var autoLockOnBackground: Bool = true

    @State private var isLoading: Bool = false
    @State private var canGoBack: Bool = false
    @State private var canGoForward: Bool = false
    @State private var reloadTrigger: Bool = false
    @State private var lastError: String? = nil
    @State private var showingSettings: Bool = false
    @State private var showControlsOverlay: Bool = false

    @Environment(\.scenePhase) private var scenePhase

    var currentURL: URL {
        URL(string: serverURLString) ?? URL(string: "https://team.bellevitesse.com/admin")!
    }

    var body: some View {
        ZStack {
            if authManager.isUnlocked {
                // ── Vue Principale de l'Admin ──────────────────────────
                ZStack(alignment: .top) {
                    AdminWebView(
                        url: currentURL,
                        isLoading: $isLoading,
                        canGoBack: $canGoBack,
                        canGoForward: $canGoForward,
                        reloadTrigger: $reloadTrigger,
                        lastError: $lastError
                    )
                    .ignoresSafeArea(.all, edges: .bottom)

                    // Barre de chargement fine en haut de l'écran
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(LinearProgressViewStyle(tint: Color(red: 1.0, green: 0.78, blue: 0.27))) // #FFC845
                            .frame(height: 3)
                            .transition(.opacity)
                    }

                    // Écran d'erreur en cas de coupure réseau sur le tournage
                    if let error = lastError {
                        VStack(spacing: 20) {
                            Image(systemName: "wifi.slash")
                                .font(.system(size: 48))
                                .foregroundColor(.secondary)

                            Text("Connexion interrompue")
                                .font(.title2.bold())

                            Text(error)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)

                            Button(action: {
                                lastError = nil
                                reloadTrigger = true
                            }) {
                                Label("Réessayer la connexion", systemImage: "arrow.clockwise")
                                    .font(.headline)
                                    .foregroundColor(.black)
                                    .padding(.horizontal, 24)
                                    .padding(.vertical, 14)
                                    .background(Color(red: 1.0, green: 0.78, blue: 0.27))
                                    .cornerRadius(10)
                            }
                        }
                        .padding(40)
                        .background(
                            RoundedRectangle(cornerRadius: 16)
                                .fill(Color(UIColor.systemBackground))
                                .shadow(color: .black.opacity(0.15), radius: 20)
                        )
                        .padding(32)
                        .frame(maxWidth: 500)
                    }

                    // Bouton discret d'outils iPad (en bas à droite de l'écran)
                    VStack {
                        Spacer()
                        HStack {
                            Spacer()
                            floatingToolbar
                                .padding(.trailing, 24)
                                .padding(.bottom, 24)
                        }
                    }
                }
                .sheet(isPresented: $showingSettings) {
                    settingsSheet
                }
            } else {
                // ── Écran de Verrouillage Biométrique ───────────────────
                lockScreenView
            }
        }
        .onAppear {
            if let url = incomingURL {
                handleIncomingURL(url)
            } else {
                authManager.authenticate()
            }
        }
        .onChange(of: incomingURL) { newURL in
            if let url = newURL {
                handleIncomingURL(url)
            }
        }
        .onChange(of: scenePhase) { newPhase in
            if newPhase == .background && autoLockOnBackground {
                authManager.lock()
            }
        }
    }

    /// Traite l'ouverture d'un lien magique (Universal Link ou Custom Scheme).
    private func handleIncomingURL(_ url: URL) {
        let urlString = url.absoluteString
        if url.scheme == "bvadmin" {
            let path = (url.host ?? "") + url.path
            serverURLString = "https://team.bellevitesse.com/admin/\(path)"
        } else {
            serverURLString = urlString
        }

        authManager.isUnlocked = true
        reloadTrigger = true
        incomingURL = nil
    }

    // MARK: - Écran de Verrouillage (Design Charte Belle Vitesse)
    private var lockScreenView: some View {
        ZStack {
            Color(red: 0.08, green: 0.08, blue: 0.08) // #151515
                .ignoresSafeArea()

            VStack(spacing: 32) {
                Spacer()

                VStack(spacing: 12) {
                    Text("BELLE VITESSE")
                        .font(.system(size: 32, weight: .black, design: .default))
                        .tracking(4)
                        .foregroundColor(.white)

                    Text("SYSTÈME D'ADMINISTRATION FLOTTE & TOURNAGE")
                        .font(.system(size: 11, weight: .semibold))
                        .tracking(2)
                        .foregroundColor(Color(red: 1.0, green: 0.78, blue: 0.27)) // #FFC845
                }

                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundColor(Color(red: 0.9, green: 0.2, blue: 0.2))
                        .padding(.horizontal)
                }

                Button(action: {
                    authManager.authenticate()
                }) {
                    HStack(spacing: 14) {
                        Image(systemName: authManager.biometricType.systemImage)
                            .font(.system(size: 22))
                        Text("Déverrouiller avec \(authManager.biometricType.title)")
                            .font(.system(size: 16, weight: .bold))
                    }
                    .foregroundColor(Color(red: 0.08, green: 0.08, blue: 0.08))
                    .padding(.horizontal, 32)
                    .padding(.vertical, 16)
                    .background(Color(red: 1.0, green: 0.78, blue: 0.27))
                    .cornerRadius(12)
                    .shadow(color: Color(red: 1.0, green: 0.78, blue: 0.27).opacity(0.35), radius: 12, y: 4)
                }

                Spacer()

                Text("iPad Dédié Opérations Terrain • v1.0")
                    .font(.caption2)
                    .foregroundColor(Color.white.opacity(0.4))
                    .padding(.bottom, 16)
            }
            .padding()
        }
    }

    // MARK: - Barre d'Outils Flottante pour Tablette
    private var floatingToolbar: some View {
        HStack(spacing: 12) {
            if showControlsOverlay {
                Button(action: { reloadTrigger = true }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.primary)
                        .frame(width: 44, height: 44)
                        .background(Color(UIColor.secondarySystemBackground))
                        .clipShape(Circle())
                }

                Button(action: { showingSettings = true }) {
                    Image(systemName: "gearshape.fill")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.primary)
                        .frame(width: 44, height: 44)
                        .background(Color(UIColor.secondarySystemBackground))
                        .clipShape(Circle())
                }

                Button(action: { authManager.lock() }) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(Color(red: 0.76, green: 0.18, blue: 0.15)) // #C32F27
                        .frame(width: 44, height: 44)
                        .background(Color(UIColor.secondarySystemBackground))
                        .clipShape(Circle())
                }
            }

            Button(action: {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                    showControlsOverlay.toggle()
                }
            }) {
                Image(systemName: showControlsOverlay ? "xmark" : "slider.horizontal.3")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 48, height: 48)
                    .background(Color(red: 0.08, green: 0.08, blue: 0.08))
                    .clipShape(Circle())
                    .shadow(color: .black.opacity(0.2), radius: 8, y: 4)
            }
        }
        .padding(6)
        .background(
            Capsule()
                .fill(Color(UIColor.systemBackground).opacity(0.85))
                .shadow(color: .black.opacity(0.12), radius: 10, y: 4)
        )
    }

    // MARK: - Vue Réglages & Choix Serveur
    private var settingsSheet: some View {
        NavigationView {
            Form {
                Section(header: Text("Serveur Belle Vitesse")) {
                    Picker("Environnement", selection: $serverURLString) {
                        Text("Production (team.bellevitesse.com)")
                            .tag("https://team.bellevitesse.com/admin")
                        Text("Staging / Test")
                            .tag("https://staging.bellevitesse.com/admin")
                        Text("Développement Local (127.0.0.1:5001)")
                            .tag("http://127.0.0.1:5001/admin")
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("URL Personnalisée :")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        TextField("https://...", text: $serverURLString)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                            .keyboardType(.URL)
                    }
                }

                Section(header: Text("Sécurité sur Plateau")) {
                    Toggle("Verrouillage auto à la fermeture", isOn: $autoLockOnBackground)
                }

                Section(header: Text("Informations Tablette")) {
                    HStack {
                        Text("Type Biométrie")
                        Spacer()
                        Text(authManager.biometricType.title)
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("Version App")
                        Spacer()
                        Text("1.0.0 (Build 1)")
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("Identifiant Flotte")
                        Spacer()
                        Text(UIDevice.current.name)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Réglages iPad BV")
            .navigationBarItems(trailing: Button("Fermer") {
                showingSettings = false
                reloadTrigger = true
            })
        }
    }
}
