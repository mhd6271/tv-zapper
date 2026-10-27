package io.github.mhd6271.tvzapper;

import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.net.URI;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Holt einen Sender als SAT>IP-Stream von der FRITZ!Box (RTSP + RTP/UDP), zieht das Video aus dem
 *  Transportstrom, decodiert es mit dem Hardware-Decoder und liefert etwa 4 Graubilder pro Sekunde in halber
 *  Aufloesung (360x288 bei SD) an den Empfaenger. Nur Ober- und Unterkante (je ein Viertel) werden kopiert –
 *  dort sitzen die Senderlogos. */
final class Sensor {
    interface Frames {
        /** top/bottom: Graubild-Streifen w x (h/4), Zeile fuer Zeile. */
        void frame(byte[] top, byte[] bottom, int w, int h);

        /** Ganzes Bild klein (Viertel-Aufloesung, grau) fuer Kontrollbilder. */
        default void thumb(byte[] g, int w, int h) {
        }

        void error(String msg);
    }

    private final String url;
    private final Frames out;
    private volatile boolean running = true;
    private Thread thread;

    Sensor(String url, Frames out) {
        this.url = url;
        this.out = out;
    }

    void start() {
        thread = new Thread(this::run, "sensor");
        thread.start();
    }

    void stop() {
        running = false;
        if (thread != null) thread.interrupt();
    }

    // --- RTSP ---

    private Socket rtsp;
    private int cseq = 0;
    private String session;

    private String request(String method, String uri, String extra) throws Exception {
        String req = method + " " + uri + " RTSP/1.0\r\nCSeq: " + (++cseq) + "\r\n"
                + (session != null ? "Session: " + session + "\r\n" : "") + extra + "\r\n";
        OutputStream o = rtsp.getOutputStream();
        o.write(req.getBytes(StandardCharsets.US_ASCII));
        o.flush();
        InputStream in = rtsp.getInputStream();
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        int c, nl = 0;
        while ((c = in.read()) >= 0) {   // Kopf bis Leerzeile
            b.write(c);
            if (c == '\n') {
                if (++nl == 2) break;
            } else if (c != '\r') nl = 0;
        }
        String resp = b.toString("US-ASCII");
        Matcher len = Pattern.compile("(?i)Content-Length:\\s*(\\d+)").matcher(resp);
        if (len.find()) in.skip(Integer.parseInt(len.group(1)));
        if (!resp.startsWith("RTSP/1.0 200")) throw new Exception(method + ": " + resp.split("\r\n")[0]);
        return resp;
    }

    private void run() {
        DatagramSocket udp = null;
        MediaCodec codec = null;
        String uri = url;
        try {
            URI u = new URI(url);
            udp = new DatagramSocket(0);
            udp.setReceiveBufferSize(2 << 20);
            udp.setSoTimeout(3000);
            rtsp = new Socket();
            rtsp.connect(new InetSocketAddress(u.getHost(), u.getPort() > 0 ? u.getPort() : 554), 4000);
            rtsp.setSoTimeout(6000);
            int p = udp.getLocalPort();
            String r = request("SETUP", uri, "Transport: RTP/AVP;unicast;client_port=" + p + "-" + (p + 1) + "\r\n");
            Matcher m = Pattern.compile("(?i)Session:\\s*([^;\\r\\n]+)").matcher(r);
            if (!m.find()) throw new Exception("keine Session");
            session = m.group(1).trim();
            request("PLAY", uri, "");
            long lastKeep = System.currentTimeMillis();
            Demux demux = new Demux();
            byte[] buf = new byte[65536];
            DatagramPacket pkt = new DatagramPacket(buf, buf.length);
            long nextFrame = 0;
            while (running) {
                try {
                    udp.receive(pkt);
                } catch (SocketTimeoutException e) {
                    throw new Exception("keine Daten von der FRITZ!Box");
                }
                int off = 12 + 4 * (buf[0] & 0x0f);
                if ((buf[0] & 0x10) != 0) off += 4 + 4 * (((buf[off + 2] & 0xff) << 8) | (buf[off + 3] & 0xff));
                for (int i = off; i + 188 <= pkt.getLength(); i += 188) demux.ts(buf, i);
                // fertige Bilder an den Decoder
                byte[] au;
                while ((au = demux.poll()) != null) {
                    if (codec == null) {
                        if (!demux.hasConfig(au)) continue;   // erst ab Sequenzkopf/SPS
                        codec = MediaCodec.createDecoderByType(demux.mime);
                        MediaFormat f = MediaFormat.createVideoFormat(demux.mime, 720, 576);
                        f.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
                        codec.configure(f, null, null, 0);
                        codec.start();
                    }
                    int in = codec.dequeueInputBuffer(20_000);
                    if (in >= 0) {
                        ByteBuffer ib = codec.getInputBuffer(in);
                        ib.clear();
                        ib.put(au, 0, Math.min(au.length, ib.capacity()));
                        codec.queueInputBuffer(in, 0, Math.min(au.length, ib.capacity()), demux.pts, 0);
                    }
                }
                if (codec != null) {
                    MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
                    int o;
                    while ((o = codec.dequeueOutputBuffer(info, 0)) >= 0 || o == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                        if (o < 0) continue;
                        long now = System.currentTimeMillis();
                        if (now >= nextFrame) {
                            nextFrame = now + 250;
                            Image img = codec.getOutputImage(o);
                            if (img != null) {
                                grab(img);
                                img.close();
                            }
                        }
                        codec.releaseOutputBuffer(o, false);
                    }
                }
                if (System.currentTimeMillis() - lastKeep > 20_000) {
                    request("OPTIONS", uri, "");
                    lastKeep = System.currentTimeMillis();
                }
            }
        } catch (Exception e) {
            if (running) out.error(e.getMessage() == null ? e.toString() : e.getMessage());
        } finally {
            try {
                if (session != null && rtsp != null && rtsp.isConnected()) request("TEARDOWN", uri, "");
            } catch (Exception ignored) {
            }
            try {
                if (rtsp != null) rtsp.close();
            } catch (Exception ignored) {
            }
            if (udp != null) udp.close();
            if (codec != null) {
                try {
                    codec.stop();
                } catch (Exception ignored) {
                }
                codec.release();
            }
        }
    }

    /** Y-Ebene auf halbe Groesse mitteln (2x2, wie ffmpeg scale am Mac), oberes und unteres Viertel kopieren. */
    private void grab(Image img) {
        Image.Plane y = img.getPlanes()[0];
        ByteBuffer b = y.getBuffer();
        int rs = y.getRowStride(), ps = y.getPixelStride();
        int W = img.getWidth() / 2, H = img.getHeight() / 2, q = H / 4;
        byte[] top = new byte[W * q], bottom = new byte[W * q];
        for (int r = 0; r < q; r++) {
            int rowT = (2 * r) * rs, rowB = (2 * (H - q + r)) * rs;
            for (int x = 0; x < W; x++) {
                int c = 2 * x * ps;
                top[r * W + x] = (byte) (((b.get(rowT + c) & 0xff) + (b.get(rowT + c + ps) & 0xff)
                        + (b.get(rowT + rs + c) & 0xff) + (b.get(rowT + rs + c + ps) & 0xff)) / 4);
                bottom[r * W + x] = (byte) (((b.get(rowB + c) & 0xff) + (b.get(rowB + c + ps) & 0xff)
                        + (b.get(rowB + rs + c) & 0xff) + (b.get(rowB + rs + c + ps) & 0xff)) / 4);
            }
        }
        out.frame(top, bottom, W, H);
        if (++thumbCount % 8 == 0) {   // etwa alle 2 s
            int tw = img.getWidth() / 4, th = img.getHeight() / 4;
            byte[] t = new byte[tw * th];
            for (int r = 0; r < th; r++)
                for (int x = 0; x < tw; x++) t[r * tw + x] = b.get(4 * r * rs + 4 * x * ps);
            out.thumb(t, tw, th);
        }
    }

    private int thumbCount;

    /** Minimaler MPEG-TS-Zerleger: PAT -> PMT -> Video-PID -> PES -> Zugriffseinheiten. */
    static final class Demux {
        String mime;
        long pts;
        private int pmtPid = -1, videoPid = -1;
        private final ByteArrayOutputStream pes = new ByteArrayOutputStream();
        private byte[] ready;
        private long readyPts;

        void ts(byte[] b, int i) {
            if (b[i] != 0x47) return;
            boolean pusi = (b[i + 1] & 0x40) != 0;
            int pid = ((b[i + 1] & 0x1f) << 8) | (b[i + 2] & 0xff);
            int afc = (b[i + 3] >> 4) & 3;
            int p = i + 4;
            if (afc == 2) return;
            if (afc == 3) p += 1 + (b[p] & 0xff);
            int end = i + 188;
            if (p >= end) return;
            if (pid == 0 && pusi && pmtPid < 0) {
                p += 1 + (b[p] & 0xff);   // pointer
                int secLen = ((b[p + 1] & 0x0f) << 8) | (b[p + 2] & 0xff);
                for (int k = p + 8; k + 4 <= p + 3 + secLen - 4 && k + 4 <= end; k += 4) {
                    int prog = ((b[k] & 0xff) << 8) | (b[k + 1] & 0xff);
                    int pp = ((b[k + 2] & 0x1f) << 8) | (b[k + 3] & 0xff);
                    if (prog != 0) candidates[pp & 0x1fff] = true;
                }
            } else if (pmtPid < 0 && pusi && candidates[pid]) {
                p += 1 + (b[p] & 0xff);
                int secLen = ((b[p + 1] & 0x0f) << 8) | (b[p + 2] & 0xff);
                int infoLen = ((b[p + 10] & 0x0f) << 8) | (b[p + 11] & 0xff);
                int k = p + 12 + infoLen, stop = Math.min(p + 3 + secLen - 4, end);
                while (k + 5 <= stop) {
                    int type = b[k] & 0xff;
                    int es = ((b[k + 1] & 0x1f) << 8) | (b[k + 2] & 0xff);
                    int esLen = ((b[k + 3] & 0x0f) << 8) | (b[k + 4] & 0xff);
                    if (type == 0x02 || type == 0x01) mime = MediaFormat.MIMETYPE_VIDEO_MPEG2;
                    else if (type == 0x1b) mime = MediaFormat.MIMETYPE_VIDEO_AVC;
                    else if (type == 0x24) mime = MediaFormat.MIMETYPE_VIDEO_HEVC;
                    if (mime != null) {
                        videoPid = es;
                        pmtPid = pid;
                        break;
                    }
                    k += 5 + esLen;
                }
            } else if (pid == videoPid) {
                if (pusi) {
                    if (pes.size() > 0) {
                        byte[] all = pes.toByteArray();
                        int hl = 9 + (all.length > 8 ? all[8] & 0xff : 0);
                        if (all.length > hl) {
                            byte[] es = new byte[all.length - hl];
                            System.arraycopy(all, hl, es, 0, es.length);
                            if (ready == null) {
                                ready = es;
                                readyPts = ptsOf(all);
                            }
                        }
                    }
                    pes.reset();
                }
                pes.write(b, p, end - p);
            }
        }

        private final boolean[] candidates = new boolean[8192];

        private static long ptsOf(byte[] h) {
            if (h.length < 14 || (h[7] & 0x80) == 0) return 0;
            long v = ((long) (h[9] & 0x0e) << 29) | ((h[10] & 0xff) << 22) | ((h[11] & 0xfe) << 14)
                    | ((h[12] & 0xff) << 7) | ((h[13] & 0xfe) >> 1);
            return v * 1000 / 90;   // in Mikrosekunden
        }

        byte[] poll() {
            byte[] r = ready;
            pts = readyPts;
            ready = null;
            return r;
        }

        /** Enthaelt die Einheit einen Sequenzkopf (MPEG-2) bzw. SPS (H.264/HEVC)? */
        boolean hasConfig(byte[] a) {
            for (int k = 0; k + 4 < a.length; k++) {
                if (a[k] == 0 && a[k + 1] == 0 && a[k + 2] == 1) {
                    int t = a[k + 3] & 0xff;
                    if (MediaFormat.MIMETYPE_VIDEO_MPEG2.equals(mime) && t == 0xb3) return true;
                    if (MediaFormat.MIMETYPE_VIDEO_AVC.equals(mime) && (t & 0x1f) == 7) return true;
                    if (MediaFormat.MIMETYPE_VIDEO_HEVC.equals(mime) && ((t >> 1) & 0x3f) == 32) return true;
                }
            }
            return false;
        }
    }
}
