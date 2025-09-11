package com.example.restservice;

import com.example.restservice.service.SignManager;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.w3c.dom.Element;

import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import java.io.ByteArrayInputStream;
import java.io.StringWriter;

@RestController
@CrossOrigin(origins = "http://localhost:4200")
@RequestMapping("/api")
public class SodaController {

    @Autowired
    SignManager signManager;

    @PostMapping("/sign")
    public String signXml(@RequestBody String xmlContent) throws Exception {
        Element signedXml = signManager.SignXML(
                new ByteArrayInputStream(xmlContent.getBytes()),
                "certs/dgii_cert.p12",  // Path in resources folder
                "Desenia123"         // Certificate password
        );

        // Convert to String
        TransformerFactory tf = TransformerFactory.newInstance();
        Transformer transformer = tf.newTransformer();
        StringWriter writer = new StringWriter();
        transformer.transform(new DOMSource(signedXml), new StreamResult(writer));
        String result = writer.toString();
        return result;
    }
}
