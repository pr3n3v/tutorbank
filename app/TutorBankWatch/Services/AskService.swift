// Client for the /ask Edge Function — live DeepSeek (CLAUDE.md §2, §5, §7).
// Returns the same two-tier {summary, answer} shape as cached answers.
import Foundation

struct AskReply: Codable, Hashable {
    let summary: String
    let answer: String
    let model: String?
    let mode: String?
}

enum AskMode: String { case chat, solve }

enum AskError: LocalizedError {
    case http(Int)
    case server(String)

    var errorDescription: String? {
        switch self {
        case .http(let code): return "request failed (HTTP \(code))"
        case .server(let msg): return msg
        }
    }
}

enum AskService {
    static func ask(prompt: String, mode: AskMode, context: String? = nil) async throws -> AskReply {
        var request = URLRequest(url: Secrets.functionsBaseURL.appendingPathComponent("ask"))
        request.httpMethod = "POST"
        request.setValue(Secrets.appSharedSecret, forHTTPHeaderField: "X-App-Secret")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 90
        var body: [String: Any] = ["prompt": prompt, "mode": mode.rawValue]
        if let context, !context.isEmpty { body["context"] = context }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
            // Surface the function's {"error": ...} message when present.
            if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let msg = obj["error"] as? String {
                throw AskError.server(msg)
            }
            throw AskError.http(status)
        }
        return try JSONDecoder().decode(AskReply.self, from: data)
    }
}
