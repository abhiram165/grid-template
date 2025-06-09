// Import required modules from k6
import http from 'k6/http';
import { sleep, check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');

// Test configuration
export const options = {
  // Test scenarios
  scenarios: {
    // Scenario 1: Constant load with 10 virtual users for 30 seconds
    constant_load: {
      executor: 'constant-vus',
      vus: 10,
      duration: '30s',
    },
    // Scenario 2: Ramp-up from 0 to 20 virtual users over 20 seconds
    ramp_up: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 10 },
        { duration: '10s', target: 20 },
        { duration: '10s', target: 0 },
      ],
      startTime: '30s', // This scenario starts after the first one
    }
  },
  // Global thresholds
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests should be below 500ms
    errors: ['rate<0.1'],             // Error rate should be less than 10%
  }
};

// Default function that will be executed for each virtual user
export default function() {
  // Main page request
  const mainPage = http.get('https://test.k6.io/');
  
  // More robust checks for the main page
  const mainPageCheck = check(mainPage, {
    'status is 200': (r) => r.status === 200,
    'page contains title': (r) => r.body.includes('<title>'),
    'page contains correct content': (r) => r.body.includes('Welcome to the k6.io demo site!'),
    'response time is acceptable': (r) => r.timings.duration < 1000,
    'content type is correct': (r) => r.headers['Content-Type'] && r.headers['Content-Type'].includes('text/html'),
  });
  
  // Track errors - only count as an error if multiple checks fail
  const checksPass = Object.values(mainPageCheck).filter(val => val).length;
  const totalChecks = Object.keys(mainPageCheck).length;
  
  // If less than 60% of checks pass, count it as an error
  errorRate.add(checksPass / totalChecks < 0.6);
  
  // Track request duration
  requestDuration.add(mainPage.timings.duration);
  
  // Log information about the request
  console.log(`Main page response time: ${mainPage.timings.duration}ms`);
  
  // Sleep to simulate user reading the page (between 2 and 5 seconds)
  sleep(Math.random() * 3 + 2);
}

