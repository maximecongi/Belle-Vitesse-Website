import SwiftUI
import WebKit

/// Vue WebView hautement optimisée pour iPadOS, supportant l'Apple Pencil, la caméra et le pont JavaScript natif.
struct AdminWebView: UIViewRepresentable {
    let url: URL
    @Binding var isLoading: Bool
    @Binding var canGoBack: Bool
    @Binding var canGoForward: Bool
    @Binding var reloadTrigger: Bool
    @Binding var lastError: String?

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> WKWebView {
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true

        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences = preferences
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        // Utilise le trousseau de données persistant pour conserver les sessions et cookies
        configuration.websiteDataStore = WKWebsiteDataStore.default()

        // Injection du flag d'environnement iPad natif
        let scriptSource = "window.__IS_BV_IPAD_APP__ = true;"
        let userScript = WKUserScript(source: scriptSource, injectionTime: .atDocumentStart, forMainFrameOnly: false)
        configuration.userContentController.addUserScript(userScript)

        // Enregistrement du gestionnaire de messages JavaScript natif
        configuration.userContentController.add(context.coordinator, name: "bvBridge")

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator

        // Réglages tactiles & Apple Pencil
        webView.scrollView.bounces = true
        webView.scrollView.alwaysBounceVertical = false
        webView.isOpaque = false
        webView.backgroundColor = UIColor(named: "AdminBg") ?? UIColor(red: 0.97, green: 0.98, blue: 0.98, alpha: 1.0)
        webView.allowsBackForwardNavigationGestures = true

        // User-Agent enrichi pour iPad
        webView.customUserAgent = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 BelleVitesseAdmin/1.0"

        context.coordinator.webView = webView

        let request = URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30)
        webView.load(request)

        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        if reloadTrigger {
            DispatchQueue.main.async {
                self.reloadTrigger = false
            }
            uiView.reload()
        }

        // Si l'URL a changé (ex: changement de serveur dans les réglages)
        if let currentURL = uiView.url, currentURL.host != url.host {
            let request = URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30)
            uiView.load(request)
        }
    }

    // MARK: - Coordinator
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        var parent: AdminWebView
        weak var webView: WKWebView?

        init(_ parent: AdminWebView) {
            self.parent = parent
        }

        // ── WKScriptMessageHandler ──────────────────────────────
        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "bvBridge", let body = message.body as? [String: Any] else { return }

            let action = body["action"] as? String ?? ""
            let payload = body["payload"] as? [String: Any] ?? [:]

            switch action {
            case "haptic":
                let type = payload["type"] as? String ?? "selection"
                triggerHaptic(type)

            case "pageReady":
                print("[iPad Bridge] Page chargée : \(payload["title"] ?? "")")

            default:
                break
            }
        }

        private func triggerHaptic(_ type: String) {
            DispatchQueue.main.async {
                switch type {
                case "success":
                    let generator = UINotificationFeedbackGenerator()
                    generator.notificationOccurred(.success)
                case "warning":
                    let generator = UINotificationFeedbackGenerator()
                    generator.notificationOccurred(.warning)
                case "error":
                    let generator = UINotificationFeedbackGenerator()
                    generator.notificationOccurred(.error)
                case "medium":
                    let generator = UIImpactFeedbackGenerator(style: .medium)
                    generator.impactOccurred()
                case "heavy":
                    let generator = UIImpactFeedbackGenerator(style: .heavy)
                    generator.impactOccurred()
                default:
                    let generator = UISelectionFeedbackGenerator()
                    generator.selectionChanged()
                }
            }
        }

        // ── WKNavigationDelegate ────────────────────────────────
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            DispatchQueue.main.async {
                self.parent.isLoading = true
                self.parent.lastError = nil
            }
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            DispatchQueue.main.async {
                self.parent.isLoading = false
                self.parent.canGoBack = webView.canGoBack
                self.parent.canGoForward = webView.canGoForward
            }
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            DispatchQueue.main.async {
                self.parent.isLoading = false
                let nsError = error as NSError
                // Ignore les annulations normales de navigation
                if nsError.code != NSURLErrorCancelled {
                    self.parent.lastError = error.localizedDescription
                }
            }
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.allow)
                return
            }

            // Redirection des schémas externes (téléphone, mail, plans) vers les applications natives iOS
            if ["tel", "mailto", "facetime", "maps"].contains(url.scheme?.lowercased()) {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }

            decisionHandler(.allow)
        }

        // ── WKUIDelegate (Support Caméra iPadOS 15+) ────────────
        @available(iOS 15.0, *)
        func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
            // Accorde automatiquement la permission caméra/micro pour le domaine d'administration BV
            decisionHandler(.grant)
        }

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let alert = UIAlertController(title: "Belle Vitesse", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            findTopViewController()?.present(alert, animated: true)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let alert = UIAlertController(title: "Belle Vitesse", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Annuler", style: .cancel) { _ in completionHandler(false) })
            alert.addAction(UIAlertAction(title: "Confirmer", style: .default) { _ in completionHandler(true) })
            findTopViewController()?.present(alert, animated: true)
        }

        private func findTopViewController() -> UIViewController? {
            guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                  let window = windowScene.windows.first(where: { $0.isKeyWindow }) else {
                return nil
            }
            var topController = window.rootViewController
            while let presented = topController?.presentedViewController {
                topController = presented
            }
            return topController
        }
    }
}
