package com.example.restservice.service;

import java.io.InputStream;
import java.io.Serializable;
import java.security.KeyStore;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import javax.xml.crypto.dsig.dom.DOMSignContext;
import javax.xml.crypto.dsig.keyinfo.KeyInfo;
import javax.xml.crypto.dsig.keyinfo.KeyInfoFactory;
import javax.xml.crypto.dsig.keyinfo.X509Data;
import javax.xml.crypto.dsig.spec.C14NMethodParameterSpec;
import javax.xml.crypto.dsig.spec.TransformParameterSpec;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.w3c.dom.Element;

//Ref: https://repo1.maven.org/maven2/com/oracle/database/xml/xmlparserv2/21.8.0.0/xmlparserv2-21.8.0.0.jar
import oracle.xml.parser.v2.DOMParser;
import oracle.xml.parser.v2.XMLDocument;
//End  Ref

import javax.xml.crypto.dsig.CanonicalizationMethod;
import javax.xml.crypto.dsig.DigestMethod;
import javax.xml.crypto.dsig.Reference;
import javax.xml.crypto.dsig.SignedInfo;
import javax.xml.crypto.dsig.Transform;
import javax.xml.crypto.dsig.XMLSignature;
import javax.xml.crypto.dsig.XMLSignatureFactory;

@Service
public class SignManager {
    private static final String algorithmSignatureMethod = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256";

    /*
     *  Method  for  signing  an  XML  using  a  digital  certificate  (.p12)
     *  @param  streamXML  InputStream  of  the  xml  that  will  be  signed.
     *  @param  pathCerticate  path  to  the  digital  certificate  (file  extension .p12)
     *  @param  passwordCertificate  digital  certificate  password
     *  @param  pathSigned  Path  where  the  signed  XML  will  be  stored
     *  @throws  Exception
     */
    public Element SignXML(InputStream streamXML, String certPath, String passwordCertificate) throws Exception {
        // Load certificate from resources
        ClassPathResource certResource = new ClassPathResource(certPath);
        try (InputStream certStream = certResource.getInputStream()){
            // Create a DOM XML SignatureFactory for generating the signature
            XMLSignatureFactory fac = XMLSignatureFactory.getInstance("DOM");

            Reference ref = fac.newReference(
                    "",
                    fac.newDigestMethod(DigestMethod.SHA256, null),
                    Collections.singletonList(fac.newTransform(Transform.ENVELOPED, (TransformParameterSpec) null)),
                    null,
                    null);

            // Create the SignedInfo object
            SignedInfo si = fac.newSignedInfo(
                    fac.newCanonicalizationMethod(CanonicalizationMethod.INCLUSIVE, (C14NMethodParameterSpec) null),
                    fac.newSignatureMethod(algorithmSignatureMethod, null),
                    Collections.singletonList(ref)
            );

            // Load the p12 file from disk
            KeyStore ks  = KeyStore.getInstance("PKCS12");
            ks.load(certStream, passwordCertificate.toCharArray());
            String param = ks.aliases().nextElement();

            // Extract the data from the p12 file
            KeyStore.PrivateKeyEntry keyEntry = (KeyStore.PrivateKeyEntry) ks.getEntry(param, new KeyStore.PasswordProtection(passwordCertificate.toCharArray()));
            X509Certificate cert = (X509Certificate) keyEntry.getCertificate();
            KeyInfoFactory kinfoFactory = fac.getKeyInfoFactory();

            // Load the certificate
            List<Serializable> x509Content = new ArrayList<Serializable>();
            x509Content.add(cert);

            // Objects to extract the private key
            X509Data x509d = kinfoFactory.newX509Data(x509Content);
            KeyInfo kinfo = kinfoFactory.newKeyInfo(Collections.singletonList(x509d));

            DOMParser parser = new DOMParser();
            parser.setPreserveWhitespace(false);
            parser.parse(streamXML);
            XMLDocument xml = parser.getDocument();

            Element xmlRoot = xml.getDocumentElement();

            // Create the signing context and specify the private keys
            DOMSignContext dsc = new DOMSignContext(keyEntry.getPrivateKey(), xmlRoot);

            // Create xml signature nodes
            XMLSignature signature = fac.newXMLSignature(si, kinfo);

            // Modify the xmlRoot object by inserting the signature
            signature.sign(dsc);

            return xmlRoot;
        } catch (Exception e) {
            throw e;
        }
    }
}
