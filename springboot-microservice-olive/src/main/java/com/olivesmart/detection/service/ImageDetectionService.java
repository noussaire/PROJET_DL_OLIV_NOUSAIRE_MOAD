package com.olivesmart.detection.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.olivesmart.detection.dto.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import java.time.Duration;
import java.util.Map;

@Service
public class ImageDetectionService {
    public static final int MAX_BODY_BYTES = 12 * 1024 * 1024;
    public static final int MAX_BASE64_CHARS = 4 * ((8 * 1024 * 1024 + 2) / 3);
    private final WebClient client;
    private final ObjectMapper mapper;
    public record Result(int status, ImageAnalysisResponse body) {}

    public ImageDetectionService(WebClient.Builder builder, ObjectMapper mapper,
            @Value("${olivesmart.ai.service-url:http://localhost:8000}") String url) {
        this.client = builder.baseUrl(url).codecs(c -> c.defaultCodecs().maxInMemorySize(16 * 1024 * 1024)).build();
        this.mapper = mapper;
    }
    public Result analyze(ImageAnalysisRequest request) {
        if (request == null || request.imageBase64() == null || request.imageBase64().isEmpty()
                || request.imageId() == null || request.imageId().isEmpty() || request.imageId().length() > 64
                || (request.mode() != null && !"LIVE".equals(request.mode()))) {
            return fail(400, "Image, identifiant et mode LIVE requis.");
        }
        if (request.imageBase64().length() > MAX_BASE64_CHARS) return fail(413, "Image superieure a 8 MiB.");
        try {
            byte[] body = mapper.writeValueAsBytes(request);
            if (body.length > MAX_BODY_BYTES) return fail(413, "Corps JSON superieur a 12 MiB.");
            var response = client.post().uri("/api/v1/analyze-image").contentType(MediaType.APPLICATION_JSON)
                    .contentLength(body.length).bodyValue(body).retrieve()
                    .bodyToMono(ImageAnalysisResponse.class).timeout(Duration.ofSeconds(60)).block();
            if (!valid(response, request)) return fail(502, "Reponse IA image invalide. Aucun resultat simule utilise.");
            return new Result(200, response);
        } catch (WebClientResponseException ex) {
            String message = "Erreur HTTP du service IA image.";
            try {
                var error = mapper.readTree(ex.getResponseBodyAsString()).path("error");
                if (error.isTextual()) message = error.asText();
            } catch (Exception ignored) {}
            return fail(ex.getStatusCode().value(), message);
        } catch (Exception ex) {
            for (Throwable cause = ex; cause != null; cause = cause.getCause()) {
                if (cause instanceof java.util.concurrent.TimeoutException)
                    return fail(504, "Delai IA image depasse (60 secondes). Aucun resultat simule utilise.");
            }
            return fail(502, "Service IA image indisponible. Aucun resultat simule utilise.");
        }
    }
    private boolean valid(ImageAnalysisResponse r, ImageAnalysisRequest request) {
        if (r == null || !r.success() || !"LIVE".equals(r.mode()) || !"YOLO".equals(r.engine())
                || !"YOLO11m V1".equals(r.model()) || !"IMAGE_PIXELS".equals(r.coordinateSystem())
                || !request.imageId().equals(r.imageId()) || r.imageWidth() == null || r.imageHeight() == null
                || r.imageWidth() <= 0 || r.imageHeight() <= 0 || (long)r.imageWidth()*r.imageHeight() > 12_000_000
                || r.detections() == null || r.totalDetections() == null || r.totalDetections() != r.detections().size()
                || r.rawDetectionCount() == null || r.rawDetectionCount() < r.totalDetections()
                || r.inferenceTimeMs() == null || !Double.isFinite(r.inferenceTimeMs()) || r.inferenceTimeMs() < 0
                || r.totalTimeMs() == null || !Double.isFinite(r.totalTimeMs()) || r.totalTimeMs() < 0
                || !parametersValid(r.inferenceParameters())) return false;
        if (request.imageWidth() != null && !request.imageWidth().equals(r.imageWidth())) return false;
        if (request.imageHeight() != null && !request.imageHeight().equals(r.imageHeight())) return false;
        var ids = new java.util.HashSet<Long>();
        for (var detection : r.detections()) {
            if (detection == null || detection.id() == null || !ids.add(detection.id()) || !"YOLO".equals(detection.source())
                    || !"trees".equals(detection.className()) || !Integer.valueOf(0).equals(detection.classId())
                    || detection.confidence() == null || !Double.isFinite(detection.confidence())
                    || detection.confidence() < 0 || detection.confidence() > 1
                    || detection.bboxPx() == null || detection.bboxPx().size() != 4
                    || detection.centerPx() == null || detection.centerPx().size() != 2
                    || detection.bboxPx().stream().anyMatch(v -> v == null || !Double.isFinite(v))
                    || detection.centerPx().stream().anyMatch(v -> v == null || !Double.isFinite(v))) return false;
            var b = detection.bboxPx(); var p = detection.centerPx();
            if (!(0 <= b.get(0) && b.get(0) < b.get(2) && b.get(2) <= r.imageWidth()
                    && 0 <= b.get(1) && b.get(1) < b.get(3) && b.get(3) <= r.imageHeight()
                    && Math.abs(p.get(0) - (b.get(0)+b.get(2))/2) < 1e-5
                    && Math.abs(p.get(1) - (b.get(1)+b.get(3))/2) < 1e-5)) return false;
        }
        return true;
    }
    private boolean parametersValid(Map<String, Object> p) {
        return p != null && numeric(p, "imgsz", 1280) && numeric(p, "conf", .20)
                && numeric(p, "iou", .50) && numeric(p, "max_det", 1000) && "cpu".equals(p.get("device"));
    }
    private boolean numeric(Map<String, Object> p, String key, double expected) {
        return p.get(key) instanceof Number number && number.doubleValue() == expected;
    }
    private Result fail(int status, String error) { return new Result(status, ImageAnalysisResponse.failure(error)); }
}
