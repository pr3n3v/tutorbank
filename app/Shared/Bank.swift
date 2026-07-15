// Codable models for the /sync payload (decode with .convertFromSnakeCase).
// `variables` is intentionally not decoded until M5 (live value-swap solve).
import Foundation

struct Bank: Codable, Hashable {
    let generatedAt: String
    let subjects: [Subject]
}

struct Subject: Codable, Hashable, Identifiable {
    let id: String
    let code: String
    let name: String
    let units: [Unit]
    let assignments: [Assignment]
}

struct Assignment: Codable, Hashable, Identifiable {
    let id: String
    let title: String
    let number: Int?
    let sourceFile: String?
}

struct Unit: Codable, Hashable, Identifiable {
    let id: String
    let name: String
    let position: Int
    let questions: [Question]
}

struct Question: Codable, Hashable, Identifiable {
    let id: String
    let text: String
    let qtype: String
    let position: Int
    let assignmentId: String?
    let answers: [Answer]

    /// The row the watch shows: the unmodified default variant when present.
    var defaultAnswer: Answer? {
        answers.first(where: { $0.variant == "default" }) ?? answers.first
    }
}

struct Answer: Codable, Hashable, Identifiable {
    let id: String
    let variant: String
    let summary: String
    let answer: String?
    let finalAnswer: String?
    let followups: [Followup]?
    let diagramWatchUrl: String?
    let diagramPhoneUrl: String?
    let verified: Bool
    let confidence: Double?
}

struct Followup: Codable, Hashable {
    let q: String
    let a: String
}
