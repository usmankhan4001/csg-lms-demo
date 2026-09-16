'use client'
import React, { useState } from 'react'
import { useOrg } from '@components/Contexts/OrgContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { toast } from 'react-hot-toast'
import { Button } from '@components/ui/button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@components/ui/dialog'
import { Input } from '@components/ui/input'
import { Textarea } from '@components/ui/textarea'
import { Label } from '@components/ui/label'
import { Switch } from '@components/ui/switch'
import { Badge } from '@components/ui/badge'
import {
  Key,
  Plus,
  Copy,
  Trash2,
  RefreshCw,
  Eye,
  EyeOff,
  AlertTriangle,
  Check,
  BookOpen,
  LifeBuoy,
  GraduationCap,
  Users,
  DollarSign,
  ShieldAlert,
  Bot,
  Layers,
} from 'lucide-react'
import {
  APIToken,
  APITokenCreateRequest,
  APITokenRights,
  createAPIToken,
  getDefaultRights,
  getFullRights,
  getReadOnlyRights,
  listAPITokens,
  regenerateAPIToken,
  revokeAPIToken,
} from '@services/api_tokens/api_tokens'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import APIDocumentation from './APIDocumentation'
import FeatureGate from '@components/Dashboard/Shared/FeatureGate/FeatureGate'
import { useLHAnalytics, AnalyticsEvent } from '@services/analytics'

const OrgEditAPIAccess: React.FC = () => {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const org = useOrg() as any
  const queryClient = useQueryClient()
  const { track } = useLHAnalytics('dashboard')
  const [activeTab, setActiveTab] = useState('tokens')
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isViewDialogOpen, setIsViewDialogOpen] = useState(false)
  const [isRevokeDialogOpen, setIsRevokeDialogOpen] = useState(false)
  const [isRegenerateDialogOpen, setIsRegenerateDialogOpen] = useState(false)
  const [selectedToken, setSelectedToken] = useState<APIToken | null>(null)
  const [newTokenValue, setNewTokenValue] = useState<string | null>(null)
  const [showTokenValue, setShowTokenValue] = useState(false)
  const [copiedToken, setCopiedToken] = useState(false)

  // Create token form state
  const [tokenName, setTokenName] = useState('')
  const [tokenDescription, setTokenDescription] = useState('')
  const [tokenExpiry, setTokenExpiry] = useState('')
  const [tokenRights, setTokenRights] = useState<APITokenRights>(getDefaultRights())
  const [rightsPreset, setRightsPreset] = useState<'custom' | 'readonly' | 'full'>('readonly')

  // Fetch tokens
  const { data: tokens, isLoading } = useQuery<APIToken[]>({
    queryKey: org?.id ? ['org', org.id, 'api-tokens'] : ['api-tokens-disabled'],
    queryFn: () => listAPITokens(org.id, access_token),
    enabled: !!(org?.id && access_token),
    staleTime: 60_000,
  })

  const handleCreateToken = async () => {
    if (!tokenName.trim()) {
      toast.error('Token name is required')
      return
    }

    const loadingToast = toast.loading('Creating API token...')
    try {
      const data: APITokenCreateRequest = {
        name: tokenName.trim(),
        description: tokenDescription.trim() || null,
        rights: tokenRights,
        expires_at: tokenExpiry || null,
      }

      const response = await createAPIToken(org.id, data, access_token)

      if (response.success) {
        setNewTokenValue(response.data.token)
        setShowTokenValue(true)
        track(AnalyticsEvent.ApiTokenCreated, {
          rights_preset: rightsPreset,
          has_expiry: !!tokenExpiry,
        })
        queryClient.invalidateQueries({ queryKey: ['org', org.id, 'api-tokens'] })
        toast.success('API token created successfully', { id: loadingToast })
        // Reset form
        setTokenName('')
        setTokenDescription('')
        setTokenExpiry('')
        setTokenRights(getDefaultRights())
      } else {
        const errorMsg =
          typeof response.data?.detail === 'string'
            ? response.data.detail
            : Array.isArray(response.data?.detail)
              ? response.data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
              : response.data?.message || 'Failed to create token'
        toast.error(errorMsg, { id: loadingToast })
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to create token', { id: loadingToast })
    }
  }

  const handleRevokeToken = async () => {
    if (!selectedToken) return

    const loadingToast = toast.loading('Revoking API token...')
    try {
      const response = await revokeAPIToken(org.id, selectedToken.token_uuid, access_token)

      if (response.success) {
        queryClient.invalidateQueries({ queryKey: ['org', org.id, 'api-tokens'] })
        toast.success('API token revoked successfully', { id: loadingToast })
        setIsRevokeDialogOpen(false)
        setSelectedToken(null)
      } else {
        toast.error(response.data?.detail || 'Failed to revoke token', { id: loadingToast })
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to revoke token', { id: loadingToast })
    }
  }

  const handleRegenerateToken = async () => {
    if (!selectedToken) return

    const loadingToast = toast.loading('Regenerating API token...')
    try {
      const response = await regenerateAPIToken(org.id, selectedToken.token_uuid, access_token)

      if (response.success) {
        setNewTokenValue(response.data.token)
        setShowTokenValue(true)
        queryClient.invalidateQueries({ queryKey: ['org', org.id, 'api-tokens'] })
        toast.success('API token regenerated successfully', { id: loadingToast })
      } else {
        toast.error(response.data?.detail || 'Failed to regenerate token', { id: loadingToast })
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to regenerate token', { id: loadingToast })
    }
  }

  const handlePresetChange = (preset: 'custom' | 'readonly' | 'full') => {
    setRightsPreset(preset)
    if (preset === 'readonly') {
      setTokenRights(getReadOnlyRights())
    } else if (preset === 'full') {
      setTokenRights(getFullRights())
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedToken(true)
    toast.success('Copied to clipboard')
    setTimeout(() => setCopiedToken(false), 2000)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <FeatureGate feature="api_access">
      <div className="flex flex-col gap-6 p-4 sm:p-8 max-w-7xl mx-auto w-full">
        {/* Header Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="border bg-white rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
                <Key size={20} />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wider">Active API Tokens</p>
                <p className="text-2xl font-bold text-gray-900">{tokens?.filter((t) => t.is_active).length || 0}</p>
              </div>
            </div>
          </div>
          <div className="border bg-white rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-green-50 text-green-600 rounded-lg">
                <Layers size={20} />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wider">Covered SMS & LMS Modules</p>
                <p className="text-2xl font-bold text-gray-900">18 Domains</p>
              </div>
            </div>
          </div>
          <div className="border bg-white rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-purple-50 text-purple-600 rounded-lg">
                <Bot size={20} />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wider">Granular Scope Enforcers</p>
                <p className="text-2xl font-bold text-gray-900">37 URN Scopes</p>
              </div>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b pb-4">
            <TabsList className="bg-gray-100/80 p-1">
              <TabsTrigger value="tokens" className="flex items-center gap-2">
                <Key size={15} />
                <span>API Tokens</span>
              </TabsTrigger>
              <TabsTrigger value="documentation" className="flex items-center gap-2">
                <BookOpen size={15} />
                <span>Interactive API Explorer & Docs</span>
              </TabsTrigger>
            </TabsList>

            {activeTab === 'tokens' && (
              <Button
                onClick={() => {
                  setTokenRights(getReadOnlyRights())
                  setRightsPreset('readonly')
                  setIsCreateDialogOpen(true)
                }}
                className="flex items-center gap-2 shadow-sm"
              >
                <Plus size={16} />
                <span>Create API Token</span>
              </Button>
            )}
          </div>

          <TabsContent value="tokens" className="pt-4">
            <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
              {isLoading ? (
                <div className="p-12 text-center text-gray-500">
                  <RefreshCw className="animate-spin mx-auto mb-2" size={24} />
                  <p>Loading API tokens...</p>
                </div>
              ) : tokens && tokens.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50/75">
                      <TableHead>Token Name</TableHead>
                      <TableHead>Token Prefix</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Used</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tokens.map((token) => (
                      <TableRow key={token.id} className="hover:bg-gray-50/50">
                        <TableCell>
                          <div>
                            <p className="font-semibold text-gray-900">{token.name}</p>
                            {token.description && (
                              <p className="text-xs text-gray-500 truncate max-w-xs">{token.description}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs font-mono">
                            {token.token_prefix}...
                          </code>
                        </TableCell>
                        <TableCell>
                          {token.is_active ? (
                            <Badge className="bg-green-50 text-green-700 border-green-200">Active</Badge>
                          ) : (
                            <Badge variant="secondary" className="bg-red-50 text-red-700 border-red-200">
                              Revoked
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-gray-600">
                          {token.last_used_at ? formatDate(token.last_used_at) : 'Never'}
                        </TableCell>
                        <TableCell className="text-sm text-gray-600">
                          {token.expires_at ? formatDate(token.expires_at) : 'Never (Permanent)'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              title="View Details"
                              onClick={() => {
                                setSelectedToken(token)
                                setIsViewDialogOpen(true)
                              }}
                            >
                              <Eye size={15} />
                            </Button>
                            {token.is_active && (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  title="Regenerate Token"
                                  onClick={() => {
                                    setSelectedToken(token)
                                    setIsRegenerateDialogOpen(true)
                                  }}
                                >
                                  <RefreshCw size={15} />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                  title="Revoke Token"
                                  onClick={() => {
                                    setSelectedToken(token)
                                    setIsRevokeDialogOpen(true)
                                  }}
                                >
                                  <Trash2 size={15} />
                                </Button>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-16 px-4">
                  <Key size={48} className="mx-auto mb-3 text-gray-400" />
                  <h3 className="text-lg font-bold text-gray-900 mb-1">No API tokens generated</h3>
                  <p className="text-sm text-gray-500 max-w-sm mx-auto mb-6">
                    Create API tokens with granular SMS and LMS scopes to securely connect custom integrations, biometric IoT turnstiles, and portals.
                  </p>
                  <Button
                    onClick={() => {
                      setTokenRights(getReadOnlyRights())
                      setRightsPreset('readonly')
                      setIsCreateDialogOpen(true)
                    }}
                  >
                    <Plus size={16} className="mr-2" /> Create First API Token
                  </Button>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="documentation" className="pt-4">
            <APIDocumentation />
          </TabsContent>
        </Tabs>

        {/* Create Token Dialog */}
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader className="px-6 pt-6">
              <DialogTitle>Generate Organization API Token</DialogTitle>
              <DialogDescription>
                Configure token identity and granular permissions across all native LMS and SMS operational modules.
              </DialogDescription>
            </DialogHeader>

            {newTokenValue ? (
              <div className="px-6 pb-6 space-y-5">
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="text-amber-600 flex-shrink-0 mt-0.5" size={22} />
                    <div>
                      <p className="font-bold text-amber-900">Copy your API Secret Key now!</p>
                      <p className="text-sm text-amber-800 mt-0.5">
                        For security reasons, this token secret is never stored in plaintext and will never be shown again.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Bearer API Token Secret</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showTokenValue ? 'text' : 'password'}
                      value={newTokenValue}
                      readOnly
                      className="font-mono text-sm bg-gray-50 font-medium"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setShowTokenValue(!showTokenValue)}
                    >
                      {showTokenValue ? <EyeOff size={16} /> : <Eye size={16} />}
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => copyToClipboard(newTokenValue)}
                    >
                      {copiedToken ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
                    </Button>
                  </div>
                </div>

                <DialogFooter>
                  <Button
                    onClick={() => {
                      setIsCreateDialogOpen(false)
                      setNewTokenValue(null)
                      setShowTokenValue(false)
                    }}
                  >
                    Done & Close
                  </Button>
                </DialogFooter>
              </div>
            ) : (
              <div className="px-6 pb-6 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="tokenName">Token Identifier / Name <span className="text-red-500">*</span></Label>
                    <Input
                      id="tokenName"
                      value={tokenName}
                      onChange={(e) => setTokenName(e.target.value)}
                      placeholder="e.g. Biometric Turnstile Sync, Mobile App Bridge"
                      maxLength={100}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="tokenExpiry">Expiration Date (Optional)</Label>
                    <Input
                      id="tokenExpiry"
                      type="datetime-local"
                      value={tokenExpiry}
                      onChange={(e) => setTokenExpiry(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="tokenDescription">Integration Purpose & Description</Label>
                  <Textarea
                    id="tokenDescription"
                    value={tokenDescription}
                    onChange={(e) => setTokenDescription(e.target.value)}
                    placeholder="Describe what external service or automated script will use this token..."
                    maxLength={500}
                    rows={2}
                  />
                </div>

                <div className="space-y-3 pt-2">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b pb-2">
                    <Label className="text-sm font-bold text-gray-900">Module Access & Permissions Matrix</Label>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant={rightsPreset === 'readonly' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handlePresetChange('readonly')}
                      >
                        Read-Only Preset
                      </Button>
                      <Button
                        type="button"
                        variant={rightsPreset === 'full' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handlePresetChange('full')}
                      >
                        Full Access (*)
                      </Button>
                      <Button
                        type="button"
                        variant={rightsPreset === 'custom' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handlePresetChange('custom')}
                      >
                        Custom Scope Matrix
                      </Button>
                    </div>
                  </div>

                  <PermissionsEditor rights={tokenRights} onChange={setTokenRights} />
                </div>

                <DialogFooter className="pt-3 border-t">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateToken}>Generate API Token</Button>
                </DialogFooter>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* View Token Dialog */}
        <Dialog open={isViewDialogOpen} onOpenChange={setIsViewDialogOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader className="px-6 pt-6">
              <DialogTitle>API Token Inspection</DialogTitle>
            </DialogHeader>
            {selectedToken && (
              <div className="px-6 pb-6 space-y-4">
                <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-xl">
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Token Name</Label>
                    <p className="font-bold text-gray-900">{selectedToken.name}</p>
                  </div>
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Status</Label>
                    <p>
                      {selectedToken.is_active ? (
                        <Badge className="bg-green-100 text-green-800">Active</Badge>
                      ) : (
                        <Badge className="bg-red-100 text-red-800">Revoked</Badge>
                      )}
                    </p>
                  </div>
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Prefix</Label>
                    <code className="font-mono text-sm bg-white border px-2 py-0.5 rounded">
                      {selectedToken.token_prefix}...
                    </code>
                  </div>
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Created Date</Label>
                    <p className="text-sm">{formatDate(selectedToken.creation_date)}</p>
                  </div>
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Last Activity</Label>
                    <p className="text-sm">
                      {selectedToken.last_used_at ? formatDate(selectedToken.last_used_at) : 'Never'}
                    </p>
                  </div>
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Expiration</Label>
                    <p className="text-sm">
                      {selectedToken.expires_at ? formatDate(selectedToken.expires_at) : 'Permanent'}
                    </p>
                  </div>
                </div>

                {selectedToken.description && (
                  <div>
                    <Label className="text-gray-500 text-xs uppercase">Description</Label>
                    <p className="text-sm bg-gray-50 p-3 rounded-lg mt-1">{selectedToken.description}</p>
                  </div>
                )}

                {selectedToken.rights && (
                  <div>
                    <Label className="text-gray-500 text-xs uppercase mb-2 block">Authorized Domain Rights</Label>
                    <PermissionsViewer rights={selectedToken.rights} />
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Revoke Token Dialog */}
        <Dialog open={isRevokeDialogOpen} onOpenChange={setIsRevokeDialogOpen}>
          <DialogContent>
            <DialogHeader className="px-6 pt-6">
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <AlertTriangle size={20} />
                Revoke API Token
              </DialogTitle>
              <DialogDescription>
                Are you sure you want to revoke this API token? Any client application or automated script using it will immediately be rejected with 401 Unauthorized.
              </DialogDescription>
            </DialogHeader>
            <div className="px-6 pb-6">
              {selectedToken && (
                <div className="bg-gray-50 rounded-lg p-3 mb-4">
                  <p className="font-semibold text-gray-900">{selectedToken.name}</p>
                  <code className="text-xs text-gray-600 font-mono">{selectedToken.token_prefix}...</code>
                </div>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsRevokeDialogOpen(false)}>
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleRevokeToken}>
                  Confirm Revocation
                </Button>
              </DialogFooter>
            </div>
          </DialogContent>
        </Dialog>

        {/* Regenerate Token Dialog */}
        <Dialog open={isRegenerateDialogOpen} onOpenChange={setIsRegenerateDialogOpen}>
          <DialogContent>
            <DialogHeader className="px-6 pt-6">
              <DialogTitle className="flex items-center gap-2">
                <RefreshCw size={20} />
                Regenerate API Token Secret
              </DialogTitle>
              <DialogDescription>
                This will rotate the secret key for this token. The old token value will stop working immediately.
              </DialogDescription>
            </DialogHeader>
            <div className="px-6 pb-6">
              {newTokenValue ? (
                <div className="space-y-4">
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <p className="font-bold text-amber-900">New Token Secret Generated!</p>
                    <p className="text-sm text-amber-800 mt-1">
                      Store this new key safely now. It will not be shown again.
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Input
                      type={showTokenValue ? 'text' : 'password'}
                      value={newTokenValue}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setShowTokenValue(!showTokenValue)}
                    >
                      {showTokenValue ? <EyeOff size={16} /> : <Eye size={16} />}
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => copyToClipboard(newTokenValue)}
                    >
                      {copiedToken ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
                    </Button>
                  </div>
                  <DialogFooter>
                    <Button
                      onClick={() => {
                        setIsRegenerateDialogOpen(false)
                        setNewTokenValue(null)
                        setShowTokenValue(false)
                        setSelectedToken(null)
                      }}
                    >
                      Done
                    </Button>
                  </DialogFooter>
                </div>
              ) : (
                <>
                  {selectedToken && (
                    <div className="bg-gray-50 rounded-lg p-3 mb-4">
                      <p className="font-medium">{selectedToken.name}</p>
                      <code className="text-sm text-gray-600 font-mono">{selectedToken.token_prefix}...</code>
                    </div>
                  )}
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsRegenerateDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleRegenerateToken}>Rotate Secret</Button>
                  </DialogFooter>
                </>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </FeatureGate>
  )
}

interface DomainSection {
  title: string
  icon: any
  resources: Array<{ key: string; label: string; hasCrud?: boolean }>
}

const PERMISSION_DOMAINS: DomainSection[] = [
  {
    title: 'SMS Academics & LMS Core',
    icon: GraduationCap,
    resources: [
      { key: 'sms_academic', label: 'Academic Structures & Sections', hasCrud: true },
      { key: 'sms_attendance', label: 'Biometric & Daily Attendance', hasCrud: true },
      { key: 'sms_gradebook', label: 'Master Gradebook & SpeedGrader', hasCrud: true },
      { key: 'sms_exams', label: 'CBT Exams & Psychometrics', hasCrud: true },
      { key: 'courses', label: 'LMS Courses & Syllabi', hasCrud: true },
      { key: 'activities', label: 'Interactive Activities & Blocks', hasCrud: true },
      { key: 'assignments', label: 'Coursework Submissions', hasCrud: true },
      { key: 'coursechapters', label: 'Course Modules & Chapters', hasCrud: true },
      { key: 'certifications', label: 'Accredited Certifications', hasCrud: true },
    ],
  },
  {
    title: 'Admissions & RevOps CRM',
    icon: Users,
    resources: [
      { key: 'sms_admissions', label: 'Inquiries, Leads & Matriculation', hasCrud: true },
    ],
  },
  {
    title: 'Financials, Tuition & Progressive Payroll',
    icon: DollarSign,
    resources: [
      { key: 'sms_fees', label: 'Tuition Vouchers & Fee Invoices', hasCrud: true },
      { key: 'sms_financials', label: 'General Ledger & Journal Entries', hasCrud: true },
      { key: 'sms_payroll', label: 'Progressive Payroll Runs & Payslips', hasCrud: true },
      { key: 'sms_hr', label: 'Staff Contracts & Faculty Roster', hasCrud: true },
      { key: 'payments', label: 'Payment Transactions & Gateways', hasCrud: true },
    ],
  },
  {
    title: 'Pastoral Care, Safety & Cognia Compliance',
    icon: ShieldAlert,
    resources: [
      { key: 'sms_pastoral', label: 'Pastoral Care & Disciplinary Logs', hasCrud: true },
      { key: 'sms_counseling', label: 'Clinical Desk (Encrypted Notes)', hasCrud: true },
      { key: 'sms_cognia', label: 'Cognia Standards & AMI Index', hasCrud: true },
    ],
  },
  {
    title: 'AI Companion, Operations & System',
    icon: Bot,
    resources: [
      { key: 'ai_tutor', label: 'Socratic AI Tutor & Knowledge Graph', hasCrud: true },
      { key: 'sms_library', label: 'School Library & Book Loans', hasCrud: true },
      { key: 'sms_transport', label: 'Transport Fleet & Route Telemetry', hasCrud: true },
      { key: 'ems_roles', label: 'Dynamic RBAC Roles & Scopes', hasCrud: true },
      { key: 'webhooks', label: 'Webhook Endpoints & Events', hasCrud: true },
      { key: 'usergroups', label: 'User Groups & Class Roster', hasCrud: true },
      { key: 'media', label: 'Media Library & Artifacts', hasCrud: true },
      { key: 'folders', label: 'Folder Storage', hasCrud: true },
      { key: 'search', label: 'Global Semantic Search', hasCrud: false },
    ],
  },
]

// Permissions Editor Component
const PermissionsEditor: React.FC<{
  rights: APITokenRights
  onChange: (_rights: APITokenRights) => void
}> = ({ rights, onChange }) => {
  const togglePermission = (resource: string, permission: string) => {
    const newRights = { ...rights }
    const resourceRights = { ...((newRights as any)[resource] || {}) }
    resourceRights[permission] = !resourceRights[permission]
    ;(newRights as any)[resource] = resourceRights
    onChange(newRights)
  }

  return (
    <div className="space-y-4 max-h-[450px] overflow-y-auto pr-1">
      {PERMISSION_DOMAINS.map((domain, idx) => (
        <div key={idx} className="border rounded-xl overflow-hidden bg-white shadow-xs">
          <div className="bg-gray-50/80 px-4 py-2.5 border-b flex items-center gap-2">
            <domain.icon size={16} className="text-gray-700" />
            <span className="text-xs font-bold uppercase tracking-wider text-gray-700">{domain.title}</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="bg-white hover:bg-white text-xs">
                <TableHead className="w-1/2">Resource</TableHead>
                <TableHead className="text-center w-1/8">Create</TableHead>
                <TableHead className="text-center w-1/8">Read</TableHead>
                <TableHead className="text-center w-1/8">Update</TableHead>
                <TableHead className="text-center w-1/8">Delete</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {domain.resources.map((resource) => (
                <TableRow key={resource.key} className="hover:bg-gray-50/60 text-sm">
                  <TableCell className="font-medium text-gray-900 py-2.5">{resource.label}</TableCell>
                  {resource.hasCrud !== false ? (
                    <>
                      <TableCell className="text-center py-2.5">
                        <Switch
                          checked={(rights as any)[resource.key]?.action_create || false}
                          onCheckedChange={() => togglePermission(resource.key, 'action_create')}
                        />
                      </TableCell>
                      <TableCell className="text-center py-2.5">
                        <Switch
                          checked={(rights as any)[resource.key]?.action_read || false}
                          onCheckedChange={() => togglePermission(resource.key, 'action_read')}
                        />
                      </TableCell>
                      <TableCell className="text-center py-2.5">
                        <Switch
                          checked={(rights as any)[resource.key]?.action_update || false}
                          onCheckedChange={() => togglePermission(resource.key, 'action_update')}
                        />
                      </TableCell>
                      <TableCell className="text-center py-2.5">
                        <Switch
                          checked={(rights as any)[resource.key]?.action_delete || false}
                          onCheckedChange={() => togglePermission(resource.key, 'action_delete')}
                        />
                      </TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell className="text-center text-gray-300">-</TableCell>
                      <TableCell className="text-center py-2.5">
                        <Switch
                          checked={rights.search?.action_read || false}
                          onCheckedChange={() => togglePermission('search', 'action_read')}
                        />
                      </TableCell>
                      <TableCell className="text-center text-gray-300">-</TableCell>
                      <TableCell className="text-center text-gray-300">-</TableCell>
                    </>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ))}
    </div>
  )
}

// Permissions Viewer Component
const PermissionsViewer: React.FC<{ rights: APITokenRights }> = ({ rights }) => {
  const getSummary = (res: any) => {
    if (!res) return '-'
    const p = []
    if (res.action_create) p.push('C')
    if (res.action_read) p.push('R')
    if (res.action_update) p.push('U')
    if (res.action_delete) p.push('D')
    return p.length > 0 ? p.join('') : '-'
  }

  const items = [
    { label: 'Academic Structures', val: getSummary(rights.sms_academic) },
    { label: 'Attendance', val: getSummary(rights.sms_attendance) },
    { label: 'Gradebook', val: getSummary(rights.sms_gradebook) },
    { label: 'CBT Exams', val: getSummary(rights.sms_exams) },
    { label: 'Admissions', val: getSummary(rights.sms_admissions) },
    { label: 'Tuition Fees', val: getSummary(rights.sms_fees) },
    { label: 'Financials', val: getSummary(rights.sms_financials) },
    { label: 'Payroll', val: getSummary(rights.sms_payroll) },
    { label: 'HR / Staff', val: getSummary(rights.sms_hr) },
    { label: 'Pastoral Care', val: getSummary(rights.sms_pastoral) },
    { label: 'Clinical Desk', val: getSummary(rights.sms_counseling) },
    { label: 'Cognia AMI', val: getSummary(rights.sms_cognia) },
    { label: 'AI Tutor', val: getSummary(rights.ai_tutor) },
    { label: 'Roles & Scopes', val: getSummary(rights.ems_roles) },
    { label: 'Webhooks', val: getSummary(rights.webhooks) },
    { label: 'Courses', val: getSummary(rights.courses) },
    { label: 'Activities', val: getSummary(rights.activities) },
    { label: 'Assignments', val: getSummary(rights.assignments) },
    { label: 'Payments', val: getSummary(rights.payments) },
    { label: 'Search', val: rights.search?.action_read ? 'R' : '-' },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-gray-50 p-3 rounded-xl border text-xs">
      {items.map((item, idx) => (
        <div key={idx} className="flex justify-between items-center py-1 px-2 rounded bg-white border border-gray-100">
          <span className="text-gray-600 font-medium truncate">{item.label}</span>
          <span className="font-mono font-bold text-gray-900 bg-gray-100 px-1.5 py-0.5 rounded text-[11px]">
            {item.val}
          </span>
        </div>
      ))}
    </div>
  )
}

export default OrgEditAPIAccess
