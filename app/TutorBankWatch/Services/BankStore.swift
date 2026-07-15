// Offline-first cache (CLAUDE.md §2, §7): the whole bank + watch PNGs live in
// Application Support; cached content opens with ZERO network. Sync is best-effort.
import Foundation
import SwiftUI

@MainActor
final class BankStore: ObservableObject {
    @Published private(set) var bank: Bank?
    @Published private(set) var isSyncing = false
    @Published private(set) var lastSync: Date?
    @Published private(set) var lastError: String?

    private let fileManager = FileManager.default

    private var supportDir: URL {
        let dir = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TutorBank", isDirectory: true)
        try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private var bankFile: URL { supportDir.appendingPathComponent("bank.json") }
    private var diagramsDir: URL {
        let dir = supportDir.appendingPathComponent("diagrams", isDirectory: true)
        try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    init() {
        loadCached()
    }

    func loadCached() {
        guard let data = try? Data(contentsOf: bankFile) else { return }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        bank = try? decoder.decode(Bank.self, from: data)
    }

    func diagramFile(for answerID: String) -> URL {
        diagramsDir.appendingPathComponent("\(answerID).png")
    }

    func diagramImage(for answerID: String) -> UIImage? {
        UIImage(contentsOfFile: diagramFile(for: answerID).path)
    }

    func sync() async {
        guard !isSyncing else { return }
        isSyncing = true
        lastError = nil
        defer { isSyncing = false }
        do {
            let (fresh, raw) = try await SyncService.fetchBank()
            try raw.write(to: bankFile, options: .atomic)
            bank = fresh
            let failed = await downloadDiagrams(for: fresh)
            pruneDiagrams(keeping: diagramAnswerIDs(in: fresh))
            lastSync = Date()
            // Partial failure must be visible — a silently missing diagram mid-lesson
            // is worse than a warning here.
            lastError = failed > 0 ? "\(failed) diagram(s) failed to download" : nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    /// Watch PNGs only — signed URLs are short-lived, so download during sync.
    /// Returns the number of failed downloads.
    private func downloadDiagrams(for bank: Bank) async -> Int {
        var failed = 0
        for subject in bank.subjects {
            for unit in subject.units {
                for question in unit.questions {
                    for answer in question.answers {
                        guard let urlString = answer.diagramWatchUrl,
                              let url = URL(string: urlString) else { continue }
                        do {
                            try await SyncService.downloadPNG(
                                from: url,
                                to: diagramFile(for: answer.id)
                            )
                        } catch {
                            failed += 1
                        }
                    }
                }
            }
        }
        return failed
    }

    private func diagramAnswerIDs(in bank: Bank) -> Set<String> {
        var ids = Set<String>()
        for subject in bank.subjects {
            for unit in subject.units {
                for question in unit.questions {
                    for answer in question.answers where answer.diagramWatchUrl != nil {
                        ids.insert(answer.id)
                    }
                }
            }
        }
        return ids
    }

    /// Diagrams removed upstream must not keep rendering from the cache.
    private func pruneDiagrams(keeping ids: Set<String>) {
        let keep = Set(ids.map { "\($0).png" })
        guard let files = try? fileManager.contentsOfDirectory(atPath: diagramsDir.path)
        else { return }
        for file in files where !keep.contains(file) {
            try? fileManager.removeItem(at: diagramsDir.appendingPathComponent(file))
        }
    }
}
