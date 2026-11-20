package com.olivesmart.detection.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.olivesmart.detection.dto.ParcelAnalysisResponse;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ModelMetadataTest {
    @Test void additiveMetadataSurvivesJsonAndLegacyPayloadStillWorks() throws Exception {
        var mapper = new ObjectMapper();
        var payload = """
            {"success":true,"mode":"LIVE","engine":"YOLO+OPENCV","model":"YOLO11m V1",
             "totalTrees":0,"trees":[],"analysisMetadata":{"yoloRawCount":3,
             "yoloInPolygonCount":2,"hybridCount":0,"yoloRawTrees":[{"confidence":0.8}],
             "inferenceParameters":{"imgsz":1280,"conf":0.2,"iou":0.5,"max_det":1000,"device":"cpu"}}}
            """;
        var response = mapper.readValue(payload, ParcelAnalysisResponse.class);
        var json = mapper.readTree(mapper.writeValueAsString(response));
        assertEquals(3, json.at("/analysisMetadata/yoloRawCount").asInt());
        assertEquals(1280, json.at("/analysisMetadata/inferenceParameters/imgsz").asInt());
        assertEquals(1, json.at("/analysisMetadata/yoloRawTrees").size());
        var old = mapper.readValue("{\"totalTrees\":0,\"trees\":[]}", ParcelAnalysisResponse.class);
        assertNull(old.analysisMetadata());
        assertEquals(0, old.totalTrees());
    }
}
