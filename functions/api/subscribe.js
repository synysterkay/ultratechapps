/**
 * Cloudflare Pages Function - Newsletter Subscription
 * Handles email signups and adds to Mailgun mailing list
 */

export async function onRequestPost(context) {
  const { request, env } = context;
  
  // CORS headers
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };
  
  try {
    // Parse request body
    const body = await request.json();
    const email = body.email?.trim();
    const niche = body.niche || 'general';
    
    if (!email || !email.includes('@')) {
      return new Response(
        JSON.stringify({ error: 'Invalid email address' }),
        { status: 400, headers: corsHeaders }
      );
    }
    
    // Get Mailgun credentials from environment variables
    const apiKey = env.MAILGUN_API_KEY;
    const domain = env.MAILGUN_DOMAIN || 'bestaiapps.site';
    const mailingList = `subscribers@${domain}`;
    
    // Prepare subscriber data with journey tracking
    const subscriberData = {
      address: email,
      subscribed: 'yes',
      upsert: 'yes',
      vars: JSON.stringify({
        subscribed_at: new Date().toISOString(),
        source: 'bestaiapps.site',
        status: 'active',
        niche: niche,
        sequence_stage: 'welcome',
        welcome_day: 0,
        last_email_sent: null,
        emails_received: 0,
        opens: 0,
        clicks: 0
      })
    };
    
    // Add to Mailgun mailing list
    const formData = new URLSearchParams(subscriberData);
    const mailgunUrl = `https://api.mailgun.net/v3/lists/${mailingList}/members`;
    
    const mailgunResponse = await fetch(mailgunUrl, {
      method: 'POST',
      headers: {
        'Authorization': 'Basic ' + btoa('api:' + apiKey),
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: formData
    });
    
    if (mailgunResponse.ok) {
      return new Response(
        JSON.stringify({
          success: true,
          message: 'Successfully subscribed!'
        }),
        { status: 200, headers: corsHeaders }
      );
    } else {
      const error = await mailgunResponse.text();
      console.error('Mailgun error:', error);
      
      return new Response(
        JSON.stringify({
          error: 'Failed to subscribe. Please try again.'
        }),
        { status: 500, headers: corsHeaders }
      );
    }
    
  } catch (error) {
    console.error('Subscription error:', error);
    
    return new Response(
      JSON.stringify({
        error: 'Server error. Please try again later.'
      }),
      { status: 500, headers: corsHeaders }
    );
  }
}

// Handle OPTIONS for CORS preflight
export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    }
  });
}
