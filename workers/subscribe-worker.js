/**
 * Cloudflare Worker for email subscriptions
 * Deploy this as a Worker, then add a route for bestaiapps.site/api/*
 */

// Use environment variables - set these in Cloudflare Workers dashboard
// or via wrangler secret put MAILGUN_API_KEY
const MAILGUN_DOMAIN = 'bestaiapps.site';
const MAILING_LIST = `subscribers@${MAILGUN_DOMAIN}`;

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default {
  async fetch(request, env) {
    // Get API key from environment
    const MAILGUN_API_KEY = env.MAILGUN_API_KEY;
    
    if (!MAILGUN_API_KEY) {
      return new Response(JSON.stringify({ error: 'Configuration error' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
    
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // Only accept POST
    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    try {
      const { email, niche } = await request.json();

      // Validate
      if (!email || !email.includes('@')) {
        return new Response(JSON.stringify({ error: 'Valid email required' }), {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      // Use environment variables if available, fallback to hardcoded
      const apiKey = env.MAILGUN_API_KEY || MAILGUN_API_KEY;
      const domain = env.MAILGUN_DOMAIN || MAILGUN_DOMAIN;
      const mailingList = `subscribers@${domain}`;

      // Add to Mailgun mailing list
      const response = await fetch(
        `https://api.mailgun.net/v3/lists/${mailingList}/members`,
        {
          method: 'POST',
          headers: {
            'Authorization': 'Basic ' + btoa(`api:${apiKey}`),
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams({
            address: email,
            subscribed: 'yes',
            vars: JSON.stringify({
              niche: niche || 'general',
              source: 'website',
              sequence_stage: 'welcome',
              subscribed_at: new Date().toISOString()
            })
          })
        }
      );

      if (response.ok) {
        return new Response(JSON.stringify({ 
          success: true, 
          message: 'Subscribed successfully!' 
        }), {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      } else if (response.status === 400) {
        // Already subscribed
        return new Response(JSON.stringify({ 
          success: true, 
          message: 'You are already subscribed!' 
        }), {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      } else {
        const error = await response.text();
        console.error('Mailgun error:', error);
        return new Response(JSON.stringify({ 
          error: 'Subscription failed. Please try again.' 
        }), {
          status: 500,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
    } catch (err) {
      console.error('Worker error:', err);
      return new Response(JSON.stringify({ error: 'Server error' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};
