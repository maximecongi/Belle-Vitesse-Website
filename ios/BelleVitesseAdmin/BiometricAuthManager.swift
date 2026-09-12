import Foundation
import LocalAuthentication
import SwiftUI

/// Gestionnaire d'authentification biométrique (Face ID / Touch ID) pour iPadOS.
/// Sécurise l'accès à l'application Belle Vitesse sur les plateaux de tournage.
@MainActor
final class BiometricAuthManager: ObservableObject {
    #if targetEnvironment(simulator)
    @Published var isUnlocked: Bool = true
    #else
    @Published var isUnlocked: Bool = false
    #endif
    @Published var errorMessage: String?
    @Published var biometricType: BiometricType = .none

    enum BiometricType {
        case faceID
        case touchID
        case none

        var title: String {
            switch self {
            case .faceID: return "Face ID"
            case .touchID: return "Touch ID"
            case .none: return "Code d'accès"
            }
        }

        var systemImage: String {
            switch self {
            case .faceID: return "faceid"
            case .touchID: return "touchid"
            case .none: return "lock.fill"
            }
        }
    }

    init() {
        checkBiometricType()
    }

    /// Détecte le matériel biométrique disponible sur l'iPad.
    func checkBiometricType() {
        let context = LAContext()
        var error: NSError?

        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            switch context.biometryType {
            case .faceID:
                self.biometricType = .faceID
            case .touchID:
                self.biometricType = .touchID
            default:
                self.biometricType = .none
            }
        } else {
            self.biometricType = .none
        }
    }

    /// Déclenche l'authentification Face ID ou Touch ID avec repli sur le code iPad.
    func authenticate() {
        let context = LAContext()
        context.localizedCancelTitle = "Annuler"
        context.localizedFallbackTitle = "Utiliser le code iPad"

        var error: NSError?
        // On autorise le repli sur le code de verrouillage de l'iPad (.deviceOwnerAuthentication)
        let policy: LAPolicy = .deviceOwnerAuthentication
        let reason = "Authentifiez-vous pour accéder à l'administration Belle Vitesse."

        if context.canEvaluatePolicy(policy, error: &error) {
            context.evaluatePolicy(policy, localizedReason: reason) { [weak self] success, evalError in
                Task { @MainActor in
                    if success {
                        self?.isUnlocked = true
                        self?.errorMessage = nil
                    } else {
                        if let evalError = evalError as? LAError, evalError.code != .userCancel {
                            self?.errorMessage = evalError.localizedDescription
                        }
                    }
                }
            }
        } else {
            // Aucun verrouillage matériel configuré sur l'iPad
            self.isUnlocked = true
        }
    }

    /// Verrouille immédiatement l'application (appelé lors de la mise en arrière-plan).
    func lock() {
        self.isUnlocked = false
        self.errorMessage = nil
    }
}
