import fetch from 'node-fetch';
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import redis from 'async-redis';

const app = express();
const client = createRedisClient();

function createRedisClient() {
    const isDocker = process.env.DOCKER === 'true';

    const redisHost = isDocker ? 'redis' : '127.0.0.1';

    const client = redis.createClient({ host: redisHost, port: 6379 });

    client.on('error', (err) => {
        console.error('Redis connection error:', err);
        setTimeout(createRedisClient, 1000);
    });

    return client;
}

app.use('/events', createProxyMiddleware({ target: 'http://172.17.144.1:5000', changeOrigin: true }));
app.use('/teams', createProxyMiddleware({ target: 'http://172.17.144.1:5001', changeOrigin: true }));
app.use('/players', createProxyMiddleware({ target: 'http://172.17.144.1:5002', changeOrigin: true }));
app.use('/stats', createProxyMiddleware({ target: 'http://172.17.144.1:5003', changeOrigin: true }));
app.use('/flights', createProxyMiddleware({ target: 'http://172.17.144.1:5004', changeOrigin: true }));
app.use('/origins', createProxyMiddleware({ target: 'http://172.17.144.1:5005', changeOrigin: true }));
app.use('/destinations', createProxyMiddleware({ target: 'http://172.17.144.1:5006', changeOrigin: true }));
app.use('/airlines', createProxyMiddleware({ target: 'http://172.17.144.1:5007', changeOrigin: true }));

app.get('/health', async (req, res) => {
    try {
        const cachedHealth = await getFromCache('health');
        if (cachedHealth !== null) {
            res.status(200).json(cachedHealth);
            return;
        }

        const eventsHealth = await checkServiceHealth('http://172.17.144.1:5000');
        const teamsHealth = await checkServiceHealth('http://172.17.144.1:5001');
        const playersHealth = await checkServiceHealth('http://172.17.144.1:5002');
        const statsHealth = await checkServiceHealth('http://172.17.144.1:5003');
        const flightsHealth = await checkServiceHealth('http://172.17.144.1:5004');
        const originsHealth = await checkServiceHealth('http://172.17.144.1:5005');
        const destinationsHealth = await checkServiceHealth('http://172.17.144.1:5006');
        const airlinesHealth = await checkServiceHealth('http://172.17.144.1:5007');

        const healthStatus = {
            status: 'healthy',
            events: eventsHealth,
            teams: teamsHealth,
            players: playersHealth,
            stats: statsHealth,
            flights: flightsHealth,
            origins: originsHealth,
            destinations: destinationsHealth,
            airlines: airlinesHealth,
        };

        await setToCache('health', healthStatus, 60);

        res.status(200).json(healthStatus);
    } catch (error) {
        console.error('Health check failed', error);
        res.status(500).json({ status: 'unhealthy', error: error.message });
    }
});

async function getFromCache(key) {
    try {
        const cachedData = await client.get(key);
        return cachedData ? JSON.parse(cachedData) : null;
    } catch (error) {
        console.error('Error fetching from cache', error);
        return null;
    }
}

async function setToCache(key, value, expiresInSeconds) {
    try {
        await client.setex(key, expiresInSeconds, JSON.stringify(value));
    } catch (error) {
        console.error('Error setting to cache', error);
    }
}

async function checkServiceHealth(target) {
    try {
        const response = await fetch(target + '/health');
        return response.ok;
    } catch (error) {
        return false;
    }
}

let currentServiceIndex = 0;

const serviceUrlsForEvents = [
    'http://172.17.144.1:5000',
    'http://172.17.144.1:5001',
    'http://172.17.144.1:5002',
    'http://172.17.144.1:5003'
];

app.get('/aggregate-events', async (req, res) => {
    try {
        const aggregatedData = {};

        for (let i = 0; i < serviceUrlsForEvents.length; i++) {
            const serviceUrlForEvents = getNextServiceUrlForEvents();
            const endpoint = getEndpointForServiceForEvents(i);

            const response = await fetch(`${serviceUrlForEvents}/${endpoint}`);
            const data = await response.json();

            aggregatedData[endpoint] = data;
        }

        res.status(200).json(aggregatedData);
    } catch (error) {
        console.error('Aggregated request failed', error);
        res.status(500).json({ status: 'error', error: error.message });
    }
});

function getNextServiceUrlForEvents() {
    const url = serviceUrlsForEvents[currentServiceIndex];
    currentServiceIndex = (currentServiceIndex + 1) % serviceUrlsForEvents.length;
    return url;
}

function getEndpointForServiceForEvents(index) {
    const endpoints = ['events', 'teams', 'players', 'stats'];
    return endpoints[index];
}

const serviceUrlsForFlights = [
    'http://172.17.144.1:5004',
    'http://172.17.144.1:5005',
    'http://172.17.144.1:5006',
    'http://172.17.144.1:5007'
];

app.get('/aggregate-flights', async (req, res) => {
    try {
        const aggregatedData = {};

        for (let i = 0; i < serviceUrlsForFlights.length; i++) {
            const serviceUrlForFlights = getNextServiceUrlForFlights();
            const endpoint = getEndpointForServiceForFlights(i);

            const response = await fetch(`${serviceUrlForFlights}/${endpoint}`);
            const data = await response.json();

            aggregatedData[endpoint] = data;
        }

        res.status(200).json(aggregatedData);
    } catch (error) {
        console.error('Aggregated request failed', error);
        res.status(500).json({ status: 'error', error: error.message });
    }
});

function getNextServiceUrlForFlights() {
    const url = serviceUrlsForFlights[currentServiceIndex];
    currentServiceIndex = (currentServiceIndex + 1) % serviceUrlsForFlights.length;
    return url;
}

function getEndpointForServiceForFlights(index) {
    const endpoints = ['flights', 'origins', 'destinations', 'airlines'];
    return endpoints[index];
}

const serviceUrlsForAll = [
    'http://172.17.144.1:5000',
    'http://172.17.144.1:5001',
    'http://172.17.144.1:5002',
    'http://172.17.144.1:5003',
    'http://172.17.144.1:5004',
    'http://172.17.144.1:5005',
    'http://172.17.144.1:5006',
    'http://172.17.144.1:5007'
];

app.get('/aggregate-all', async (req, res) => {
    try {
        const aggregatedData = {};

        for (let i = 0; i < serviceUrlsForAll.length; i++) {
            const serviceUrlForAll = getNextServiceUrlForAll();
            const endpoint = getEndpointForServiceForAll(i);

            const response = await fetch(`${serviceUrlForAll}/${endpoint}`);
            const data = await response.json();

            aggregatedData[endpoint] = data;
        }

        res.status(200).json(aggregatedData);
    } catch (error) {
        console.error('Aggregated request failed', error);
        res.status(500).json({ status: 'error', error: error.message });
    }
});

function getNextServiceUrlForAll() {
    const url = serviceUrlsForAll[currentServiceIndex];
    currentServiceIndex = (currentServiceIndex + 1) % serviceUrlsForAll.length;
    return url;
}

function getEndpointForServiceForAll(index) {
    const endpoints = ['events', 'teams', 'players', 'stats', 'flights', 'origins', 'destinations', 'airlines'];
    return endpoints[index];
}

const PORT = 7000;
app.listen(PORT, '0.0.0.0',() => console.log(`Gateway listening on port ${PORT}`));