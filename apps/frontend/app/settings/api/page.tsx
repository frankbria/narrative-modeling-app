'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { ProductionService, APIKeyInfo, CreateAPIKeyRequest } from '@/lib/services/production'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import * as AlertDialog from '@radix-ui/react-alert-dialog'
import {
  Key, 
  Loader2, 
  Plus, 
  Trash2, 
  Copy, 
  Check,
  Calendar,
  Activity,
  AlertCircle,
  Info
} from 'lucide-react'
import { useRouter } from 'next/navigation'

export default function APIKeysPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const [apiKeys, setApiKeys] = useState<APIKeyInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteKeyId, setDeleteKeyId] = useState<string | null>(null)
  
  // Create API Key Dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [copiedKey, setCopiedKey] = useState(false)
  
  // Form state
  const [keyName, setKeyName] = useState('')
  const [keyDescription, setKeyDescription] = useState('')
  const [rateLimit, setRateLimit] = useState([1000])
  const [hasExpiry, setHasExpiry] = useState(false)
  const [expiryDays, setExpiryDays] = useState([30])

  useEffect(() => {
    if (session) {
      fetchAPIKeys()
    }
  }, [session])

  const fetchAPIKeys = async () => {
    try {
      setIsLoading(true)
      const token = await getAuthToken()
      const keys = await ProductionService.listAPIKeys(token)
      setApiKeys(keys)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load API keys')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateKey = async () => {
    if (!keyName.trim()) {
      setError('Please provide a name for the API key')
      return
    }

    setIsCreating(true)
    setError(null)

    try {
      const token = await getAuthToken()
      
      const request: CreateAPIKeyRequest = {
        name: keyName,
        description: keyDescription || undefined,
        rate_limit: rateLimit[0],
        expires_in_days: hasExpiry ? expiryDays[0] : undefined
      }

      const response = await ProductionService.createAPIKey(request, token)
      setNewApiKey(response.api_key)
      
      // Refresh the list
      await fetchAPIKeys()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create API key')
    } finally {
      setIsCreating(false)
    }
  }

  const handleDeleteKey = async (keyId: string) => {
    try {
      const token = await getAuthToken()
      await ProductionService.revokeAPIKey(keyId, token)
      await fetchAPIKeys()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke API key')
    }
    setDeleteKeyId(null)
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(true)
      setTimeout(() => setCopiedKey(false), 2000)
    } catch (err) {
      setError('Failed to copy to clipboard')
    }
  }

  const resetCreateForm = () => {
    setKeyName('')
    setKeyDescription('')
    setRateLimit([1000])
    setHasExpiry(false)
    setExpiryDays([30])
    setNewApiKey(null)
    setCopiedKey(false)
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">
              Please log in to manage API keys
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin mr-3 text-primary" />
        <span className="text-lg">Loading API keys...</span>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Key className="h-8 w-8" />
            API Keys
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage API keys for production model deployment
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={(open) => {
          setShowCreateDialog(open)
          if (!open) resetCreateForm()
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create API Key
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Create New API Key</DialogTitle>
              <DialogDescription>
                Generate a new API key for accessing your deployed models
              </DialogDescription>
            </DialogHeader>

            {!newApiKey ? (
              <div className="space-y-4 py-4">
                {error && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                <div className="space-y-2">
                  <Label htmlFor="name">Key Name *</Label>
                  <Input
                    id="name"
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    placeholder="Production API Key"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={keyDescription}
                    onChange={(e) => setKeyDescription(e.target.value)}
                    placeholder="What will this key be used for?"
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Rate Limit: {rateLimit[0]} requests/hour</Label>
                  <Slider
                    value={rateLimit}
                    onValueChange={setRateLimit}
                    min={100}
                    max={10000}
                    step={100}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Label htmlFor="has-expiry">Set Expiration Date</Label>
                  <Switch
                    id="has-expiry"
                    checked={hasExpiry}
                    onCheckedChange={setHasExpiry}
                  />
                </div>

                {hasExpiry && (
                  <div className="space-y-2">
                    <Label>Expires in: {expiryDays[0]} days</Label>
                    <Slider
                      value={expiryDays}
                      onValueChange={setExpiryDays}
                      min={1}
                      max={365}
                      step={1}
                    />
                  </div>
                )}

                <Button 
                  className="w-full" 
                  onClick={handleCreateKey}
                  disabled={isCreating || !keyName.trim()}
                >
                  {isCreating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    'Create API Key'
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-4 py-4">
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Your API key has been created. Copy it now - you won't be able to see it again!
                  </AlertDescription>
                </Alert>

                <div className="space-y-2">
                  <Label>Your API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      value={newApiKey}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={() => copyToClipboard(newApiKey)}
                    >
                      {copiedKey ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                <div className="bg-muted p-4 rounded-lg space-y-2">
                  <h4 className="font-medium">Quick Start</h4>
                  <p className="text-sm text-muted-foreground">
                    Use this API key in your applications:
                  </p>
                  <pre className="bg-background p-2 rounded text-xs overflow-x-auto">
{`curl -X POST \\
  ${process.env.NEXT_PUBLIC_API_URL}/api/v1/production/v1/models/{model_id}/predict \\
  -H "X-API-Key: ${newApiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"data": [{"feature1": 1, "feature2": "value"}]}'`}
                  </pre>
                </div>

                <Button 
                  className="w-full" 
                  onClick={() => setShowCreateDialog(false)}
                >
                  Done
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {error && !showCreateDialog && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* API Keys Table */}
      {apiKeys.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64 space-y-4">
            <Key className="h-16 w-16 text-muted-foreground" />
            <div className="text-center">
              <h3 className="text-lg font-semibold">No API Keys Yet</h3>
              <p className="text-muted-foreground mt-1">
                Create your first API key to start using your models in production
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Your API Keys</CardTitle>
            <CardDescription>
              Manage API keys for accessing your deployed models
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Rate Limit</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {apiKeys.map((key) => (
                  <TableRow key={key.key_id}>
                    <TableCell className="font-medium">{key.name}</TableCell>
                    <TableCell className="max-w-xs truncate">
                      {key.description || '-'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={key.is_active ? 'default' : 'secondary'}>
                        {key.is_active ? 'Active' : 'Revoked'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Activity className="h-3 w-3" />
                        <span className="text-sm">{key.total_requests}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{key.rate_limit}/hr</span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span className="text-sm">
                          {new Date(key.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {key.expires_at ? (
                        <span className="text-sm">
                          {new Date(key.expires_at).toLocaleDateString()}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">Never</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setDeleteKeyId(key.key_id)}
                        disabled={!key.is_active}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <AlertDialog.Root open={!!deleteKeyId} onOpenChange={() => setDeleteKeyId(null)}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-lg focus:outline-none">
            <AlertDialog.Title className="text-lg font-semibold mb-2">Revoke API Key</AlertDialog.Title>
            <AlertDialog.Description className="mb-6 text-muted-foreground">
              Are you sure you want to revoke this API key? Applications using this key will no longer be able to access your models.
            </AlertDialog.Description>
            <div className="flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <Button variant="outline">Cancel</Button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <Button
                  onClick={() => deleteKeyId && handleDeleteKey(deleteKeyId)}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Revoke Key
                </Button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </div>
  )
}