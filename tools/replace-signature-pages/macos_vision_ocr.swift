import Foundation
import Vision
import AppKit

/// Local OCR via macOS Vision. Args: one or more image paths.
/// Prints recognized text for each image, separated by form-feed (\u{0c}).
/// Does not upload; fully on-device.

guard CommandLine.arguments.count > 1 else {
    fputs("usage: macos_vision_ocr <image> [image...]\n", stderr)
    exit(2)
}

let paths = Array(CommandLine.arguments.dropFirst())
var failed = 0

for (idx, path) in paths.enumerated() {
    autoreleasepool {
        let url = URL(fileURLWithPath: path)
        guard let image = NSImage(contentsOf: url),
              let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let cgImage = rep.cgImage
        else {
            fputs("failed to load image: \(path)\n", stderr)
            failed += 1
            if idx + 1 < paths.count { print("\u{0c}", terminator: "") }
            return
        }

        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        if #available(macOS 13.0, *) {
            request.recognitionLanguages = ["zh-Hans", "en-US"]
        }

        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        do {
            try handler.perform([request])
            let observations = request.results ?? []
            let lines = observations.compactMap { $0.topCandidates(1).first?.string }
            print(lines.joined(separator: "\n"), terminator: "")
        } catch {
            fputs("OCR failed for \(path): \(error)\n", stderr)
            failed += 1
        }

        if idx + 1 < paths.count {
            print("\n\u{0c}", terminator: "")
        } else {
            print("")
        }
    }
}

exit(failed == paths.count ? 3 : 0)
