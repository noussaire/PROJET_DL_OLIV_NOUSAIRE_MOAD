package com.olivesmart.detection.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.olivesmart.detection.dto.*;
import com.olivesmart.detection.service.ImageDetectionService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.concurrent.Semaphore;

@RestController
@RequestMapping("/api/v1/images")
@CrossOrigin(origins = "*")
public class ImageAnalysisController {
    private final ImageDetectionService service;
    private final ObjectMapper mapper;
    private final Semaphore admission = new Semaphore(1);
    public ImageAnalysisController(ImageDetectionService service, ObjectMapper mapper) {
        this.service = service; this.mapper = mapper;
    }
    @PostMapping("/analyser")
    public ResponseEntity<ImageAnalysisResponse> analyze(HttpServletRequest request) {
        long length = request.getContentLengthLong();
        if (length < 0) return failure(411, "Content-Length requis.");
        if (length == 0 || length > ImageDetectionService.MAX_BODY_BYTES) return failure(413, "Corps JSON vide ou superieur a 12 MiB.");
        if (request.getContentType() == null || !request.getContentType().split(";")[0].trim().equals("application/json"))
            return failure(415, "Content-Type application/json requis.");
        if (!admission.tryAcquire()) return failure(503, "Une analyse image est deja en cours.");
        try {
            byte[] body = request.getInputStream().readNBytes((int)length);
            if (body.length != length) return failure(400, "Requete tronquee.");
            var input = mapper.readValue(body, ImageAnalysisRequest.class);
            var result = service.analyze(input);
            return ResponseEntity.status(result.status()).body(result.body());
        } catch (Exception ex) {
            return failure(400, "Requete JSON image invalide.");
        } finally { admission.release(); }
    }
    private ResponseEntity<ImageAnalysisResponse> failure(int status, String error) {
        return ResponseEntity.status(status).body(ImageAnalysisResponse.failure(error));
    }
}
