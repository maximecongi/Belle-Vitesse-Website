import SwiftUI

@main
struct BelleVitesseAdminApp: App {
    @State private var incomingURL: URL?

    var body: some Scene {
        WindowGroup {
            ContentView(incomingURL: $incomingURL)
                .onOpenURL { url in
                    // Interception native des Universal Links (https://team.bellevitesse.com/admin/auth/...)
                    self.incomingURL = url
                }
        }
    }
}

