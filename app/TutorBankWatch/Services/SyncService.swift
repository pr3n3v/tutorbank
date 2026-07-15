// Talks to the Supabase Edge Functions (CLAUDE.md §2). Only /sync in M3.
import Foundation

enum SyncError: LocalizedError {
    case http(Int)

    var errorDescription: String? {
        switch self {
        case .http(let code): return "sync failed (HTTP \(code))"
        }
    }
}

enum SyncService {
    static func fetchBank() async throws -> (bank: Bank, raw: Data) {
        var request = URLRequest(url: Secrets.functionsBaseURL.appendingPathComponent("sync"))
        request.setValue(Secrets.appSharedSecret, forHTTPHeaderField: "X-App-Secret")
        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw SyncError.http(status) }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return (try decoder.decode(Bank.self, from: data), data)
    }

    static func downloadPNG(from url: URL, to destination: URL) async throws {
        let (data, response) = try await URLSession.shared.data(from: url)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw SyncError.http(status) }
        try data.write(to: destination, options: .atomic)
    }
}
