package com.olivesmart.detection.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.olivesmart.detection.controller.ImageAnalysisController;
import com.olivesmart.detection.dto.*;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.Test;
import org.springframework.http.*;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.reactive.function.client.*;
import reactor.core.publisher.Mono;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ImageApiTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private ImageAnalysisRequest request() { return new ImageAnalysisRequest("YWJj", "image-a", 120, 80, null, "LIVE"); }
    private String payload() {
        return """
            {"success":true,"mode":"LIVE","engine":"YOLO","imageId":"image-a","coordinateSystem":"IMAGE_PIXELS",
             "imageWidth":120,"imageHeight":80,"totalDetections":1,"rawDetectionCount":1,"model":"YOLO11m V1",
             "inferenceParameters":{"imgsz":1280,"conf":0.2,"iou":0.5,"max_det":1000,"device":"cpu"},
             "inferenceTimeMs":1,"totalTimeMs":2,"warnings":[],
             "detections":[{"id":1,"bboxPx":[10,10,30,30],"centerPx":[20,20],"confidence":0.8,"classId":0,"className":"trees","source":"YOLO"}]}
            """;
    }
    private ImageDetectionService service(HttpStatus status, String json) {
        return new ImageDetectionService(WebClient.builder().exchangeFunction(req -> {
            assertEquals("/api/v1/analyze-image",req.url().getPath());
            assertTrue(req.headers().getContentLength()>0);
            return Mono.just(ClientResponse.create(status).header("Content-Type","application/json").body(json).build());
        }),mapper,"http://unused.invalid");
    }
    @Test void realPixelContractPreservedThroughJava() throws Exception {
        var result=service(HttpStatus.OK,payload()).analyze(request());
        assertEquals(200,result.status());assertEquals(1,result.body().totalDetections());
        var json=mapper.readTree(mapper.writeValueAsString(result.body()));
        assertEquals(20,json.at("/detections/0/centerPx/0").asDouble());
        assertFalse(json.at("/detections/0").has("lat"));
        assertFalse(json.at("/detections/0").has("health"));
    }
    @Test void simulatedStaleAndInvalidGeometryResponsesAreRejected() {
        for(String bad:new String[]{payload().replace("\"LIVE\"","\"DEMO\""),
                payload().replace("image-a","old-image"),payload().replace("[10,10,30,30]","[10,10,130,30]"),
                payload().replace("\"source\":\"YOLO\"","\"source\":\"DEMO\"")}) {
            assertEquals(502,service(HttpStatus.OK,bad).analyze(request()).status());
        }
    }
    @Test void zeroDetectionsAreAccepted() {
        try {
            var tree=mapper.readTree(payload());
            ((com.fasterxml.jackson.databind.node.ObjectNode)tree).put("totalDetections",0).put("rawDetectionCount",0)
                .set("detections",mapper.createArrayNode());
            var result=service(HttpStatus.OK,tree.toString()).analyze(request());
            assertEquals(200,result.status());assertTrue(result.body().detections().isEmpty());
        } catch(Exception ex) {fail(ex);}
    }
    @Test void pythonErrorsAndTimeoutsNeverBecomeDemo() {
        var result=service(HttpStatus.PAYLOAD_TOO_LARGE,"{\"error\":\"12 millions de pixels\"}").analyze(request());
        assertEquals(413,result.status());assertFalse(result.body().success());assertEquals("NONE",result.body().engine());
        var timed=new ImageDetectionService(WebClient.builder().exchangeFunction(req->Mono.error(new java.util.concurrent.TimeoutException())),mapper,"http://unused.invalid");
        assertEquals(504,timed.analyze(request()).status());
        var offline=new ImageDetectionService(WebClient.builder().exchangeFunction(req->Mono.error(new IllegalStateException("offline"))),mapper,"http://unused.invalid");
        assertEquals(502,offline.analyze(request()).status());
    }
    @Test void bodyLimitCheckedBeforeReadingAndRouteWorks() throws Exception {
        var controller=new ImageAnalysisController(service(HttpStatus.OK,payload()),mapper);
        var large=mock(HttpServletRequest.class);
        when(large.getContentLengthLong()).thenReturn((long)ImageDetectionService.MAX_BODY_BYTES+1);
        assertEquals(413,controller.analyze(large).getStatusCode().value());verify(large,never()).getInputStream();
        var req=new MockHttpServletRequest();req.setContentType("application/json");req.setContent(mapper.writeValueAsBytes(request()));
        assertEquals(200,controller.analyze(req).getStatusCode().value());
    }
}
