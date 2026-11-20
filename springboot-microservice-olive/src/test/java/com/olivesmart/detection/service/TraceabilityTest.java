package com.olivesmart.detection.service;

import com.olivesmart.detection.controller.ParcelAnalysisController;
import com.olivesmart.detection.dto.ParcelAnalysisRequest;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import static org.junit.jupiter.api.Assertions.*;

class TraceabilityTest {
    private ParcelAnalysisRequest request(String mode, String modelType) {
        return new ParcelAnalysisRequest(null, java.util.List.of(), 0.05, modelType, mode);
    }

    private OliveDetectionService response(HttpStatus status, String json) {
        return new OliveDetectionService(WebClient.builder().exchangeFunction(req -> Mono.just(
                ClientResponse.create(status).header("Content-Type", MediaType.APPLICATION_JSON_VALUE).body(json).build())),
                new RayCastingGeofenceService(), "http://unused.invalid");
    }

    private String payload(String trees, int count) {
        return """
                {"success":true,"mode":"LIVE","engine":"YOLO+OPENCV","model":"best.pt (YOLOv8n)",
                 "totalTrees":%d,"trees":%s}
                """.formatted(count, trees);
    }

    @Test void pythonErrorNeverCreatesFictionalTrees() {
        var service = response(HttpStatus.INTERNAL_SERVER_ERROR, "{\"error\":\"failed\"}");
        var result = service.analyzeParcel(request("LIVE", "PROF_EXACT_9"));
        assertFalse(result.success());
        assertTrue(result.trees().isEmpty());
        assertEquals(0, result.totalTrees());
        assertNotNull(result.error());
        assertEquals(502, new ParcelAnalysisController(service).analyserParcelle(request("LIVE", null)).getStatusCode().value());
    }

    @Test void connectionFailureNeverCreatesFictionalTrees() {
        var service = new OliveDetectionService(WebClient.builder().exchangeFunction(req -> Mono.error(new IllegalStateException("offline"))),
                new RayCastingGeofenceService(), "http://unused.invalid");
        var result = service.analyzeParcel(request("LIVE", null));
        assertFalse(result.success());
        assertTrue(result.trees().isEmpty());
    }

    @Test void emptySuccessfulResponseIsAccepted() {
        var service = response(HttpStatus.OK, payload("[]", 0));
        assertTrue(service.analyzeParcel(request("LIVE", null)).success());
        assertEquals(200, new ParcelAnalysisController(service).analyserParcelle(request("LIVE", null)).getStatusCode().value());
    }

    @Test void yoloAndOpenCvSurviveDtoRoundTrip() throws Exception {
        var service = response(HttpStatus.OK, payload("""
            [{"id":1,"source":"YOLO","sources":["YOLO","OPENCV"],"detectionEngine":"YOLO+OPENCV"},
             {"id":2,"source":"OPENCV","sources":["OPENCV"],"detectionEngine":"OPENCV"}]
            """, 2));
        var result = service.analyzeParcel(request("LIVE", null));
        assertTrue(result.success());
        assertEquals("YOLO", result.trees().get(0).source());
        assertEquals(java.util.List.of("YOLO", "OPENCV"), result.trees().get(0).sources());
        assertEquals("OPENCV", result.trees().get(1).source());
        var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
        var roundTrip = mapper.readTree(mapper.writeValueAsString(result));
        assertEquals("OPENCV", roundTrip.get("trees").get(1).get("source").asText());
    }

    @Test void demoRequiresExplicitModeAndDoesNotCallPython() {
        var service = new OliveDetectionService(WebClient.builder().exchangeFunction(req -> {throw new AssertionError("DEMO must not call Python");}),
                new RayCastingGeofenceService(), "http://unused.invalid");
        var result = service.analyzeParcel(request("DEMO", "PROF_EXACT_9"));
        assertTrue(result.success());
        assertEquals("DEMO", result.engine());
        assertEquals(9, result.totalTrees());
        assertTrue(result.trees().stream().allMatch(t -> "DEMO".equals(t.source())));
    }

    @Test void demoOrLegacyPythonResponseCannotPassAsLive() {
        assertFalse(response(HttpStatus.OK, "{\"totalTrees\":0,\"trees\":[]}").analyzeParcel(request("LIVE", null)).success());
        var mixed = payload("[{\"source\":\"YOLO\",\"sources\":[\"YOLO\",\"DEMO\"]}]", 1);
        assertFalse(response(HttpStatus.OK, mixed).analyzeParcel(request("LIVE", null)).success());
    }
}
