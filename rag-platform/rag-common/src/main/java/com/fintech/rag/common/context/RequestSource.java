package com.fintech.rag.common.context;

/**
 * 请求来源。用于区分两套完全不同的鉴权与限流体系。
 *
 * <p>识别依据是 DMZ 网关注入的请求头 {@code X-Request-Source}：</p>
 * <ul>
 *   <li>携带且值为 {@code DMZ_GATEWAY} → 外网前端用户流量，走用户令牌体系</li>
 *   <li>不携带 → SF 内网业务微服务流量，走应用 AppKey 签名体系</li>
 * </ul>
 *
 * @author rag-platform
 */
public enum RequestSource {

    /** DMZ 网关转发的前端用户请求 */
    DMZ_WEB("DMZ_GATEWAY", "外网前端用户"),

    /** SF 内网业务微服务直连请求 */
    SF_INNER_APP(null, "SF内网业务微服务");

    /** 网关注入该 Header 时使用的固定值 */
    public static final String DMZ_HEADER_VALUE = "DMZ_GATEWAY";

    private final String headerValue;
    private final String description;

    RequestSource(String headerValue, String description) {
        this.headerValue = headerValue;
        this.description = description;
    }

    public String getHeaderValue() {
        return headerValue;
    }

    public String getDescription() {
        return description;
    }

    /**
     * 根据请求头值解析来源。
     *
     * <p>注意：本方法只做「标记解析」，不做「真伪校验」。
     * 真伪校验（IP 白名单 / 网关签名）在各服务的鉴权拦截器中完成，
     * 否则内网调用方伪造该头即可冒充前端。</p>
     */
    public static RequestSource resolve(String headerValue) {
        return DMZ_HEADER_VALUE.equals(headerValue) ? DMZ_WEB : SF_INNER_APP;
    }
}
