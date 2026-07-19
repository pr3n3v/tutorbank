// Codable models for the /sync payload (decode with .convertFromSnakeCase).
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
    let variables: [Variable]?
    let answers: [Answer]

    /// The row the watch shows: the unmodified default variant when present.
    var defaultAnswer: Answer? {
        answers.first(where: { $0.variant == "default" }) ?? answers.first
    }

    var hasVariables: Bool { !(variables ?? []).isEmpty }

    var isCode: Bool { qtype == "program" || qtype == "predict_output" }
}

/// A value-swap template variable, e.g. {"name":"a","default":3}. `default` may
/// arrive as a JSON number or string; we keep a string form for the input field.
struct Variable: Codable, Hashable, Identifiable {
    let name: String
    let defaultText: String

    var id: String { name }

    private enum CodingKeys: String, CodingKey { case name, defaultText = "default" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        if let d = try? c.decode(Double.self, forKey: .defaultText) {
            defaultText = d == d.rounded() ? String(Int(d)) : String(d)
        } else if let s = try? c.decode(String.self, forKey: .defaultText) {
            defaultText = s
        } else {
            defaultText = ""
        }
    }
}

struct Answer: Codable, Hashable, Identifiable {
    let id: String
    let variant: String
    let summary: String
    let answer: String?
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
